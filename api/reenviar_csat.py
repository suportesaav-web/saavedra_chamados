# reenviar_csat.py - Script para reenvio em massa de emails de avaliação CSAT pendentes
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"m:\GestaoChamados\api\.env")

DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS", "WS123br")
DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")

CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"
engine = create_engine(CONN_STR)

SMTP_HOST = os.environ.get("SAAVEDRA_SMTP_HOST")
SMTP_PORT = int(os.environ.get("SAAVEDRA_SMTP_PORT", 587))
SMTP_USER = os.environ.get("SAAVEDRA_SMTP_USER")
SMTP_PASS = os.environ.get("SAAVEDRA_SMTP_PASS")
SMTP_FROM = os.environ.get("SAAVEDRA_SMTP_FROM")

def enviar_email_lembrete(destinatario, nome_usuario, tarefa_id, titulo):
    if not all([SMTP_HOST, SMTP_USER, SMTP_FROM]):
        print(f"❌ Configuração de SMTP incompleta para enviar para {destinatario}")
        return False

    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid #1e8e3e; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0; color: #1e8e3e;">⭐ Pesquisa de Satisfação de Atendimento</h3>
            <p style="font-size: 14px; color: #555;">Olá, <strong>{nome_usuario}</strong>. O seu chamado <strong>#{tarefa_id}</strong> foi concluído, mas ainda aguarda a sua avaliação de atendimento.</p>
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #1e8e3e; border-radius: 4px; margin: 20px 0;">
                <span style="font-size: 12px; color: #888; font-weight: bold;">Ticket #{tarefa_id}</span><br>
                <strong style="font-size: 15px;">{titulo}</strong>
            </div>
            <div style="background: #f0f4f8; padding: 20px; border-radius: 6px; margin-top: 20px; text-align: center;">
                <p style="margin: 0 0 12px 0; font-size: 14px; font-weight: bold; color: #25282a;">Como avalia a resolução deste suporte?</p>
                <div style="display: flex; justify-content: center; gap: 8px; flex-wrap: wrap;">
                    <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=1" style="background: #da291c; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">1 😞 Péssimo</a>
                    <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=2" style="background: #e65100; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">2 😕 Ruim</a>
                    <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=3" style="background: #f57c00; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">3 😐 Regular</a>
                    <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=4" style="background: #2e7d32; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">4 😊 Bom</a>
                    <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}&avaliar=5" style="background: #1e8e3e; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">5 🤩 Excelente</a>
                </div>
            </div>
            <div style="text-align: center; margin-top: 25px;">
                <a href="http://10.0.0.252:8082/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #25282a; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-size: 13px;">Ver Chamado no Painel</a>
            </div>
        </div>
    </div>
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[{tarefa_id}] Lembrete: Avalie o Atendimento - Saavedra"
        msg['From'] = f"Saavedra Suporte <{SMTP_FROM}>"
        msg['To'] = destinatario
        msg.attach(MIMEText(corpo_html, 'html'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.ehlo()
        if SMTP_PORT == 587:
            server.starttls()
            server.ehlo()
        if SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [destinatario], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail para {destinatario} (Ticket #{tarefa_id}): {e}")
        return False

print("🔍 Buscando chamados concluídos sem avaliação CSAT...")
with engine.connect() as conn:
    pendentes = conn.execute(text("""
        SELECT T.TAREFA_ID, T.TITULO, U.NOME, U.EMAIL 
        FROM tbTAREFAS T
        JOIN tbUSUARIO U ON T.SOLICITANTE_ID = U.USUARIO_ID
        WHERE T.STATUS_ID = 4 
          AND (T.NOTA_CSAT IS NULL OR T.NOTA_CSAT = 0)
          AND U.EMAIL IS NOT NULL AND U.EMAIL LIKE '%@%'
        ORDER BY T.TAREFA_ID DESC
    """)).fetchall()

total = len(pendentes)
print(f"📊 Foram encontrados {total} chamado(s) encerrados sem avaliação CSAT.\n")

if total == 0:
    print("✨ Nenhum chamado pendente de avaliação!")
else:
    sucessos = 0
    for idx, row in enumerate(pendentes, 1):
        t_id, titulo, u_nome, u_email = row[0], row[1], row[2], row[3]
        print(f"[{idx}/{total}] Enviando lembrete para '{u_nome}' ({u_email}) - Ticket #{t_id}...")
        ok = enviar_email_lembrete(u_email, u_nome, t_id, titulo)
        if ok:
            sucessos += 1

    print(f"\n✅ Disparo concluído com sucesso! {sucessos}/{total} e-mails enviados.")
