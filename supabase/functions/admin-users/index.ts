// CronogramaObras v0.1.6: administração de contas, só via função de borda.
// SUPABASE_SERVICE_ROLE_KEY NUNCA é enviado ao Streamlit ou ao GitHub.
import { createClient } from 'npm:@supabase/supabase-js@2';

const headers = {
  'content-type': 'application/json; charset=utf-8',
  'access-control-allow-origin': '*',
  'access-control-allow-headers': 'authorization, apikey, content-type, x-client-info',
  'access-control-allow-methods': 'POST, OPTIONS',
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers });
const VALID_ROLES = new Set(['admin', 'standard', 'viewer']);
const emailOk = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) && s.length <= 254;

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers });
  if (req.method !== 'POST') return json({ error: 'Método não permitido' }, 405);
  const url = Deno.env.get('SUPABASE_URL');
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  const publicKey = Deno.env.get('SUPABASE_ANON_KEY') ?? Deno.env.get('SUPABASE_PUBLISHABLE_KEY');
  if (!url || !serviceKey || !publicKey) return json({ error: 'Configuração do servidor incompleta' }, 503);
  const authHeader = req.headers.get('authorization') ?? '';
  const match = authHeader.match(/^Bearer\s+([^\s]+)$/i);
  if (!match) return json({ error: 'É necessário entrar como administrador' }, 401);
  try {
    const caller = createClient(url, publicKey, {
      global: { headers: { Authorization: authHeader } },
      auth: { persistSession: false, autoRefreshToken: false },
    });
    // Verificar usuário com Auth, não confiar em ID/perfil enviado pelo navegador.
    const { data: verified, error: verifyError } = await caller.auth.getUser(match[1]);
    if (verifyError || !verified.user) return json({ error: 'Sessão não autorizada' }, 401);
    const { data: access, error: accessError } = await caller.rpc('my_account_access');
    if (accessError || !access?.active || access?.role !== 'admin')
      return json({ error: 'Apenas administradores ativos podem gerenciar contas' }, 403);

    const admin = createClient(url, serviceKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    let payload: Record<string, unknown>;
    try { payload = await req.json(); }
    catch { return json({ error: 'JSON inválido' }, 400); }
    const action = String(payload.action ?? '');
    if (action === 'list') {
      const { data, error } = await admin.from('profiles')
        .select('id,email,full_name,platform_role,account_enabled,account_expires_at')
        .order('full_name');
      if (error) throw error;
      return json({ users: data ?? [] });
    }
    if (action === 'create') {
      const email = String(payload.email ?? '').trim().toLowerCase();
      const fullName = String(payload.full_name ?? '').trim();
      const password = String(payload.password ?? '');
      const role = String(payload.role ?? 'viewer');
      const expiry = payload.expires_at == null ? null : String(payload.expires_at);
      if (!emailOk(email) || fullName.length < 3 || fullName.length > 160 || password.length < 10 || !VALID_ROLES.has(role))
        return json({ error: 'Preencha e-mail, nome, senha (mínimo 10 caracteres) e perfil válido' }, 400);
      if (expiry != null && (!Number.isFinite(Date.parse(expiry)) || Date.parse(expiry) <= Date.now()))
        return json({ error: 'A validade deve ser uma data futura' }, 400);
      const { data: created, error: createError } = await admin.auth.admin.createUser({
        email, password, email_confirm: true, user_metadata: { full_name: fullName },
      });
      if (createError || !created.user) return json({ error: createError?.message ?? 'Falha ao criar conta' }, 400);
      const { error: profileError } = await admin.from('profiles').upsert({
        id: created.user.id, email, full_name: fullName, platform_role: role,
        account_enabled: true, account_expires_at: expiry,
      }, { onConflict: 'id' });
      if (profileError) {
        // A conta Auth não deve permanecer ativa sem o perfil correto.
        await admin.auth.admin.deleteUser(created.user.id);
        throw profileError;
      }
      return json({ message: 'Conta criada', id: created.user.id });
    }
    if (action === 'update') {
      const id = String(payload.id ?? '');
      const role = String(payload.role ?? '');
      const fullName = String(payload.full_name ?? '').trim();
      const enabled = payload.enabled;
      const expiry = payload.expires_at == null ? null : String(payload.expires_at);
      if (!/^[\da-f-]{36}$/i.test(id) || !VALID_ROLES.has(role) || fullName.length < 3 || fullName.length > 160 || typeof enabled !== 'boolean')
        return json({ error: 'Dados de alteração inválidos' }, 400);
      if (expiry != null && !Number.isFinite(Date.parse(expiry)))
        return json({ error: 'Data de validade inválida' }, 400);
      if (id === verified.user.id && (role !== 'admin' || !enabled || (expiry && Date.parse(expiry) <= Date.now())))
        return json({ error: 'Não é permitido retirar o próprio acesso administrativo' }, 400);
      const { data: existing, error: lookupError } = await admin.from('profiles').select('id').eq('id', id).maybeSingle();
      if (lookupError) throw lookupError;
      if (!existing) return json({ error: 'Usuário não encontrado' }, 404);
      const { error: changeError } = await admin.from('profiles')
        .update({ full_name: fullName, platform_role: role, account_enabled: enabled, account_expires_at: expiry })
        .eq('id', id);
      if (changeError) throw changeError;
      // Uma sessão JWT preexistente poderá existir até expirar, mas RLS bloqueia
      // imediatamente toda leitura e escrita após desativação/vencimento.
      return json({ message: 'Usuário atualizado' });
    }
    return json({ error: 'Ação não permitida' }, 400);
  } catch (error) {
    // Nunca retornar chaves/tokens/stack trace ao solicitante.
    console.error('Erro de administração:', error instanceof Error ? error.message : 'erro desconhecido');
    return json({ error: 'Não foi possível concluir a administração de contas' }, 500);
  }
});
