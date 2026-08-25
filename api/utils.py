import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import logging

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, FRONTEND_URL

logger = logging.getLogger("SaavedraChamadosAuditoria")

def formatar_data_segura(dt) -> Optional[str]:
    if not dt:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)

def enviar_email_background(destinatario: str, assunto: str, corpo_html: str):
    if not all([SMTP_HOST, SMTP_USER, SMTP_FROM]):
        return
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
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
    except Exception as e:
        logger.error(f"❌ [SMTP ERROR] {e}")

def enviar_email_abertura(destinatario: str, nome_usuario: str, tarefa_id: int, titulo: str):
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid #dc4405; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0;">Olá, {nome_usuario}!</h3>
            <p style="font-size: 14px; color: #555;">O seu chamado foi registrado com sucesso na nossa fila de atendimento técnico.</p>
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #dc4405; border-radius: 4px; margin: 20px 0;">
                <span style="font-size: 12px; color: #888; font-weight: bold;">Ticket #{tarefa_id}</span><br>
                <strong style="font-size: 15px;">{titulo}</strong>
            </div>
            <div style="text-align: center; margin-top: 30px;">
                <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #dc4405; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Acessar o Chamado</a>
            </div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Chamado Registrado - Saavedra", corpo_html)

def enviar_email_atualizacao(destinatario: str, nome_usuario: str, tarefa_id: int, status_nome: str, comentario: str, status_id: int):
    cor_topo = "#1e8e3e" if status_id == 4 else "#dc4405"
    bloco_csat = ""
    if status_id == 4:
        bloco_csat = f"""
        <div style="background: #f0f4f8; padding: 20px; border-radius: 6px; margin-top: 20px; text-align: center;">
            <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: bold; color: #25282a;">Como avalia este atendimento?</p>
            <div style="display: flex; justify-content: center; gap: 8px;">
                <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=1" style="background: #da291c; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">1 😞</a>
                <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=5" style="background: #1e8e3e; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">5 🤩</a>
            </div>
        </div>
        """
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid {cor_topo}; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0;">Atualização no Ticket #{tarefa_id}</h3>
            <p style="font-size: 14px; color: #555;">Olá, <strong>{nome_usuario}</strong>. Houve uma nova movimentação técnica na sua solicitação.</p>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; border: 1px solid #eaeaea;">
                <div style="margin-bottom: 12px;"><span style="font-size: 12px; color: #888;">Estado Atual:</span><br><span style="background: {cor_topo}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{status_nome}</span></div>
                <div><span style="font-size: 12px; color: #888;">Nota da Equipa Técnica:</span><p style="margin: 0; font-size: 14px; background: #ffffff; padding: 12px; border-radius: 4px; border: 1px solid #e0e0e0; white-space: pre-wrap;">{comentario}</p></div>
            </div>
            {bloco_csat}
            <div style="text-align: center; margin-top: 30px;"><a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: {cor_topo}; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Ver Detalhes</a></div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Atualização - Saavedra", corpo_html)

def enviar_email_lembrete_csat(destinatario: str, nome_usuario: str, tarefa_id: int, titulo: str):
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
                    <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=1" style="background: #da291c; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">1 😞 Péssimo</a>
                    <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=2" style="background: #e65100; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">2 😕 Ruim</a>
                    <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=3" style="background: #f57c00; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">3 😐 Regular</a>
                    <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=4" style="background: #2e7d32; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">4 😊 Bom</a>
                    <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}&avaliar=5" style="background: #1e8e3e; color: white; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 12px;">5 🤩 Excelente</a>
                </div>
            </div>
            <div style="text-align: center; margin-top: 25px;">
                <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #25282a; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-size: 13px;">Ver Chamado no Painel</a>
            </div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Lembrete: Avalie o Atendimento - Saavedra", corpo_html)

def enviar_email_atribuicao_tecnico(destinatario: str, nome_tecnico: str, tarefa_id: int, titulo: str, solicitante_nome: str):
    corpo_html = f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; color: #25282a; max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-top: 5px solid #0056b3; border-radius: 8px;">
        <div style="background: #25282a; padding: 20px; text-align: center;"><h2 style="margin: 0; color: #ffffff; font-size: 20px;">Saavedra <span style="color: #dc4405;">Chamados</span></h2></div>
        <div style="padding: 30px; background: #ffffff;">
            <h3 style="margin-top: 0;">Novo Chamado Atribuído a Você</h3>
            <p style="font-size: 14px; color: #555;">Olá, <strong>{nome_tecnico}</strong>. Você foi atribuído como responsável técnico pelo chamado abaixo:</p>
            <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #0056b3; border-radius: 4px; margin: 20px 0;">
                <span style="font-size: 12px; color: #888; font-weight: bold;">Ticket #{tarefa_id}</span><br>
                <strong style="font-size: 15px;">{titulo}</strong><br>
                <span style="font-size: 13px; color: #555;">Solicitante: {solicitante_nome}</span>
            </div>
            <div style="text-align: center; margin-top: 30px;">
                <a href="{FRONTEND_URL}/detalhe_chamado.html?id={tarefa_id}" style="display: inline-block; background: #0056b3; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 4px; font-weight: bold;">Atender Chamado</a>
            </div>
        </div>
    </div>
    """
    enviar_email_background(destinatario, f"[{tarefa_id}] Atribuição Técnico - Saavedra", corpo_html)
