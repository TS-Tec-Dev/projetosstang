-- Após executar 20261116_global_roles_kml.sql no SQL Editor, atribua o primeiro admin.
-- Substitua o e-mail abaixo pelo e-mail de SUA conta já cadastrada.
-- NÃO coloque este script com email real em repositório público.
UPDATE public.profiles
SET platform_role='admin'
WHERE lower(email)=lower('SEU_EMAIL_CADASTRADO@EXEMPLO.COM');

-- Confirme quem é administrador:
SELECT email,platform_role FROM public.profiles WHERE platform_role='admin';
