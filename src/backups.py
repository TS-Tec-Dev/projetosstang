"""Exportação e restauração pela sessão autenticada; nenhum segredo administrativo.

O ZIP contém JSON e bytes dos anexos privados. Importação cria IDs novos,
substitui autoria de comentários e não replica membros para não elevar privilégios.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from uuid import uuid4
import json
import re
import zipfile

from src.db import BUCKET, MAX_FILE_BYTES

BACKUP_VERSION = 1
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_DOCUMENTS = 400
DATA_TABLES = [
    "stages", "tasks", "task_details", "task_checklist", "execution_milestones",
    "finance_entries", "documents", "task_comments", "project_members",
]

def _fetch_all(sb, table, pid):
    rows=[]
    for offset in range(0, 100000, 500):
        order_col = 'task_id' if table == 'task_details' else ('user_id' if table == 'project_members' else 'id')
        batch = (sb.table(table).select('*').eq('project_id',pid).order(order_col)
                 .range(offset,offset+499).execute().data or [])
        rows.extend(batch)
        if len(batch)<500:
            return rows
    raise ValueError(f"Excesso de registros em {table}. Solicite exportação assistida.")


def make_backup(sb, projects, include_files=True):
    """Captura tudo do projeto autorizado via RLS, inclusive arquivos de Storage."""
    if not projects: raise ValueError('Selecione ao menos um projeto.')
    if len(projects)>25: raise ValueError('Limite de 25 projetos por backup.')
    buffer=BytesIO()
    data={"format":"cronogramaobras-cloud", "version":BACKUP_VERSION,
          "exported_at":datetime.now(timezone.utc).isoformat(),
          "files_included":bool(include_files), "projects":[]}
    total_bytes=0
    doc_count=0
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as zf:
        for project in projects:
            pid=project['id']
            snapshot={"project":dict(project),"tables":{}}
            for table in DATA_TABLES:
                snapshot['tables'][table]=_fetch_all(sb,table,pid)
            docs=snapshot['tables']['documents']
            doc_count+=len(docs)
            if doc_count>MAX_DOCUMENTS:raise ValueError('Mais de 400 anexos; divida a exportação por projeto.')
            for doc in docs:
                doc['backup_blob']=None
                doc['backup_sha256']=None
                if not include_files:continue
                raw=sb.storage.from_(BUCKET).download(doc['storage_path'])
                if not isinstance(raw,bytes): raw=bytes(raw)
                if not raw or len(raw)>MAX_FILE_BYTES:
                    raise ValueError(f"Arquivo inválido para backup: {doc.get('filename')}")
                total_bytes+=len(raw)
                if total_bytes>MAX_ARCHIVE_BYTES:
                    raise ValueError('Backup ultrapassa 200 MB de anexos. Selecione menos projetos.')
                suffix=PurePosixPath(doc.get('filename','')).suffix.lower()
                safe_suffix=suffix if re.fullmatch(r'\.[a-z0-9]{1,7}',suffix) else '.dat'
                blob_name=f'files/{uuid4().hex}{safe_suffix}'
                zf.writestr(blob_name,raw)
                doc['backup_blob']=blob_name
                doc['backup_sha256']=sha256(raw).hexdigest()
            data['projects'].append(snapshot)
        encoded=json.dumps(data,ensure_ascii=False,indent=2,default=str).encode('utf-8')
        if len(encoded)>25*1024*1024:raise ValueError('Dados do backup excedem 25 MB.')
        zf.writestr('data.json',encoded)
    result=buffer.getvalue()
    if len(result)>MAX_ARCHIVE_BYTES:
        raise ValueError('ZIP final maior que 200 MB. Divida o backup em lotes menores.')
    return result


def inspect_backup(raw):
    """Faz validações antes de qualquer escrita no Supabase."""
    if not raw or len(raw)>MAX_ARCHIVE_BYTES:
        raise ValueError('ZIP vazio ou maior que 200 MB.')
    with zipfile.ZipFile(BytesIO(raw),'r') as zf:
        names=zf.namelist()
        if len(names)>MAX_DOCUMENTS+3:
            raise ValueError('Número inesperado de itens no ZIP.')
        if 'data.json' not in names:raise ValueError('Arquivo data.json não encontrado.')
        total=sum(i.file_size for i in zf.infolist())
        if total>MAX_ARCHIVE_BYTES+25*1024*1024:
            raise ValueError('Conteúdo expandido maior que o limite seguro.')
        info=zf.getinfo('data.json')
        if info.file_size>25*1024*1024:raise ValueError('Manifesto JSON muito grande.')
        payload=json.loads(zf.read('data.json').decode('utf-8'))
        if payload.get('format')!='cronogramaobras-cloud' or payload.get('version')!=BACKUP_VERSION:
            raise ValueError('Formato/versão de backup não compatível.')
        projects=payload.get('projects')
        if not isinstance(projects,list) or not 1<=len(projects)<=25:
            raise ValueError('Lista de projetos inválida.')
        file_records=0
        for obj in projects:
            if not isinstance(obj.get('project'),dict) or not isinstance(obj.get('tables'),dict):
                raise ValueError('Estrutura incompleta no backup.')
            for t in DATA_TABLES:
                if not isinstance(obj['tables'].get(t),list):
                    raise ValueError(f'Tabela {t} ausente no backup.')
            for d in obj['tables']['documents']:
                blob=d.get('backup_blob')
                file_records+=1
                if payload.get('files_included'):
                    if not blob or not re.fullmatch(r'files/[a-f0-9]{32}\.[a-z0-9]{1,7}',blob):
                        raise ValueError('Caminho do anexo inválido.')
                    if blob not in names:raise ValueError(f'Arquivo do backup ausente: {blob}')
                    inf=zf.getinfo(blob)
                    if inf.file_size<1 or inf.file_size>MAX_FILE_BYTES:raise ValueError('Anexo com tamanho inválido.')
        if file_records>MAX_DOCUMENTS: raise ValueError('Limite de anexos excedido.')
        return payload


def _new_project(sb, snapshot, owner_id):
    from src.db import add_project_with_workflow
    project=snapshot['project']
    rows=snapshot['tables']
    stages={s['id']:s for s in rows['stages']}
    details={r['task_id']:r for r in rows['task_details']}
    # Ordem estável, única por etapa para mapear o ID de origem ao novo ID.
    counters=defaultdict(int)
    flow=[]; order_keys={}
    ordered=sorted(rows['tasks'],key=lambda t:(stages[t['stage_id']].get('sort_order',0),t.get('sort_order',0),t['id']))
    if not ordered:raise ValueError('Projeto sem tarefas não pode ser restaurado nesta versão.')
    for t in ordered:
        stage=stages.get(t['stage_id'])
        if not stage:raise ValueError('Etapa de tarefa ausente no arquivo.')
        name=stage['name']; idx=counters[name];counters[name]+=1
        order_keys[t['id']]=(name,idx)
        flow.append({
            'stage_name':name,'stage_order':int(stage.get('sort_order') or 0),
            'sort_order':idx,'title':t['title'],'description':t.get('description') or '',
            'start_date':t.get('start_date'),'due_date':t.get('due_date'),
            'template_code':(details.get(t['id']) or {}).get('template_code'),
            'checklist':[],'execution':[],
        })
    new_title=(str(project.get('title') or 'Projeto')[:164].strip()+' (restaurado)')[:180]
    new_project=add_project_with_workflow(sb,owner_id,{
        'title':new_title,'client_name':project.get('client_name') or '',
        'location':project.get('location') or '', 'description':project.get('description') or '',
        'start_date':project.get('start_date'),'target_date':project.get('target_date'),
    },flow)
    return new_project,order_keys


def restore_snapshot(sb, source, zf, owner_id):
    """Restaura um projeto como cópia nova. Retorna ID; se falhar, tenta limpeza."""
    rows=source['tables']; new_id=None
    try:
        project,order_keys=_new_project(sb,source,owner_id)
        new_id=project['id']
        new_stages=_fetch_all(sb,'stages',new_id)
        stage_ids={s['id']:s['name'] for s in rows['stages']}
        new_tasks=_fetch_all(sb,'tasks',new_id)
        new_names={s['id']:s['name'] for s in new_stages}
        by_pair={(new_names[t['stage_id']],int(t['sort_order'])):t['id'] for t in new_tasks}
        old_to_new={old:by_pair[pair] for old,pair in order_keys.items()}
        # Cópia dos campos não sensíveis do item. O status só vem após anexos.
        for t in rows['tasks']:
            sb.table('tasks').update({
                'description':t.get('description') or '',
                'priority':t.get('priority') or 'Normal',
                'start_date':t.get('start_date'), 'due_date':t.get('due_date'),
                'percent_done':int(t.get('percent_done') or 0),
                'planned_cost':float(t.get('planned_cost') or 0),
            }).eq('id',old_to_new[t['id']]).execute()
        for name in ('task_checklist','execution_milestones','finance_entries'):
            for r in rows[name]:
                if r['task_id'] not in old_to_new:raise ValueError(f'Referência inválida em {name}')
                values={k:v for k,v in r.items() if k not in ('id','project_id','task_id','created_at','updated_at')}
                values.update({'project_id':new_id,'task_id':old_to_new[r['task_id']]})
                sb.table(name).insert(values).execute()
        for d in rows['task_details']:
            sb.table('task_details').upsert({
                'project_id':new_id,'task_id':old_to_new[d['task_id']],
                'template_code':d.get('template_code') or '',
                'data':d.get('data') or {},
            },on_conflict='task_id').execute()
        for d in rows['documents']:
            blob=d.get('backup_blob')
            if not blob:continue
            raw=zf.read(blob)
            if sha256(raw).hexdigest()!=d.get('backup_sha256'):
                raise ValueError('Checksum divergente em anexo; restauração cancelada.')
            path_suffix=PurePosixPath(blob).suffix
            filename=str(d.get('filename') or 'Documento')[:250]
            target=f"{new_id}/{old_to_new[d['task_id']]}/{uuid4().hex}{path_suffix}"
            sb.storage.from_(BUCKET).upload(target,raw,{'content-type':d.get('content_type') or 'application/octet-stream','upsert':'false'})
            sb.table('documents').insert({
                'project_id':new_id,'task_id':old_to_new[d['task_id']],
                'uploaded_by':owner_id,'category':d.get('category') or 'Outro',
                'filename':filename,'storage_path':target,
                'size_bytes':len(raw),'content_type':d.get('content_type') or 'application/octet-stream',
            }).execute()
        for c in rows['task_comments']:
            if c.get('task_id') not in old_to_new:continue
            content=str(c.get('content') or '')
            attribution=f"[Importação: autor anterior {c.get('author_id','desconhecido')}]\n"
            sb.table('task_comments').insert({
                'project_id':new_id,'task_id':old_to_new[c['task_id']],
                'author_id':owner_id,'content':(attribution+content)[:2000],
            }).execute()
        for t in rows['tasks']:
            if t.get('status')!='A fazer':
                sb.table('tasks').update({'status':t['status'],'percent_done':int(t.get('percent_done') or 0)})\
                    .eq('id',old_to_new[t['id']]).execute()
        # Membros anteriores não são copiados: somente o importador vira proprietário.
        return new_id
    except Exception as exc:
        if new_id:
            try:purge_project(sb,new_id,owner_id)
            except Exception as cleanup:
                raise RuntimeError(f'Restauração incompleta no projeto {new_id}: {exc}. '
                                   f'Falha também na limpeza: {cleanup}') from exc
        raise


def restore_backup(sb, raw, owner_id, selected_indices):
    payload=inspect_backup(raw)
    if not payload.get('files_included'):
        raise ValueError('Backup sem arquivos: restauração completa indisponível. Use backup com anexos.')
    with zipfile.ZipFile(BytesIO(raw),'r') as zf:
        restored=[]
        for i in selected_indices:
            if not isinstance(i,int) or i<0 or i>=len(payload['projects']):
                raise ValueError('Seleção de projetos inválida.')
            restored.append(restore_snapshot(sb,payload['projects'][i],zf,owner_id))
    return restored


def purge_project(sb, project_id, owner_id):
    """Apaga APENAS um projeto do próprio usuário, junto com arquivos do Storage."""
    result=sb.table('projects').select('id,owner_id').eq('id',project_id).limit(1).execute().data or []
    if not result or str(result[0]['owner_id'])!=str(owner_id):
        raise PermissionError('Somente o proprietário pode excluir este projeto.')
    # Gatilho do orçamento impede remoção de último orçamento de tarefa concluída.
    # Retorna as tarefas a fazer antes da cascata para não deixar esse bloqueio.
    for t in _fetch_all(sb,'tasks',project_id):
        if t.get('status')=='Concluída':
            sb.table('tasks').update({'status':'A fazer','percent_done':0}).eq('id',t['id']).execute()
    docs=_fetch_all(sb,'documents',project_id)
    paths=[d['storage_path'] for d in docs]
    for pos in range(0,len(paths),50):
        sb.storage.from_(BUCKET).remove(paths[pos:pos+50])
    deleted=sb.table('projects').delete().eq('id',project_id).execute()
    # A política RLS não deverá ocultar uma exclusão permitida; conferência explícita.
    still_there=sb.table('projects').select('id').eq('id',project_id).limit(1).execute().data or []
    if still_there:
        raise RuntimeError('O banco não confirmou a exclusão do projeto.')
