# testar_email.py
from dotenv import load_dotenv
load_dotenv()

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 1. Carrega e exibe as configurações do .env para conferência
SMTP_HOST = os.environ.get("SAAVEDRA_SMTP_HOST")
SMTP_PORT = os.environ.get("SAAVEDRA_SMTP_PORT")
SMTP_USER = os.environ.get("SAAVEDRA_SMTP_USER")
SMTP_PASS = os.environ.get("SAAVEDRA_SMTP_PASS")
SMTP_FROM = os.environ.get("SAAVEDRA_SMTP_FROM")

print("🔍 Verificando variáveis lidas do teu arquivo .env:")
print(f"-> Host SMTP: {SMTP_HOST}")
print(f"-> Porta: {SMTP_PORT}")
print(f"-> Usuário: {SMTP_USER}")
print(f"-> Remetente: {SMTP_FROM}")
print(f"-> Senha configurada?: {'SIM' if SMTP_PASS else 'NÃO'}\n")

if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM]):
    print("❌ Erro: Faltam configurações de SMTP no teu arquivo .env!")
    exit()

# =========================================================================
# 🔴 ATENÇÃO: ALTERE O E-MAIL ABAIXO PARA O TEU E-MAIL REAL DE TESTE
# =========================================================================
EMAIL_DESTINATARIO = "jonatanfsevero@gmail.com" 
# =========================================================================

print(f"⏳ Tentando ligar e enviar e-mail de teste para: {EMAIL_DESTINATARIO}...")

try:
    port = int(SMTP_PORT)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "🧪 Saavedra Chamados - Teste de Conexão SMTP"
    msg['From'] = f"Saavedra Suporte <{SMTP_FROM}>"
    msg['To'] = EMAIL_DESTINATARIO
    
    corpo_html = """
    <html>
        <body style="font-family: Arial, sans-serif; color: #25282a; padding: 20px;">
            <div style="max-width: 500px; background: white; padding: 20px; border-top: 5px solid #dc4405; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                <h2 style="color: #dc4405; margin-top: 0;">Conexão SMTP Estabelecida!</h2>
                <p>Se recebeste este e-mail, significa que o motor em Python e as credenciais do ficheiro <strong>.env</strong> estão 100% corretos e operacionais no servidor.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 11px; color: #888;">Sistema de Gestão de Chamados Saavedra - Ambiente Local</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(corpo_html, 'html'))
    
    # Inicia a ligação SMTP com timeout de 15 segundos
    server = smtplib.SMTP(SMTP_HOST, port, timeout=15)
    server.ehlo()
    
    # Se for a porta padrão de TLS (587), ativa a encriptação obrigatória
    if port == 587:
        print("🔒 Ativando criptografia TLS (porta 587)...")
        server.starttls()
        server.ehlo()
        
    if SMTP_PASS:
        print("🔑 Efetuando autenticação de usuário...")
        server.login(SMTP_USER, SMTP_PASS)
        
    print("📤 Enviando mensagem...")
    server.sendmail(SMTP_FROM, [EMAIL_DESTINATARIO], msg.as_string())
    server.quit()
    
    print("\n✅ SUCESSO EXCEPCIONAL! O e-mail foi enviado. Verifique a sua caixa de entrada, spam ou lixo eletrônico.")

except Exception as e:
    print("\n❌ FALHA CRÍTICA AO ENVIAR E-MAIL!")
    print(f"Detalhe técnico do erro retornado pelo servidor: {e}")