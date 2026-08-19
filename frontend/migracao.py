import os
import pandas as pd
from sqlalchemy import create_engine, text
import re
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=r"../api/.env")
except ImportError:
    pass

# ==========================================
# 1. CONFIGURAÇÃO DA CONEXÃO
# ==========================================
DB_USER = os.environ.get("SAAVEDRA_DB_USER", "chamados")
DB_PASS = os.environ.get("SAAVEDRA_DB_PASS", "WS123br")
DB_HOST = os.environ.get("SAAVEDRA_DB_HOST", "10.0.0.252")
DB_NAME = os.environ.get("SAAVEDRA_DB_NAME", "GestaoChamados")

CONN_STR = f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?driver=SQL+Server"
engine = create_engine(CONN_STR)

ARQUIVO_USUARIOS = "Tarefas TI (1).xlsx - tbUSUARIO.csv"
ARQUIVO_TAREFAS = "Tarefas TI (1).xlsx - tbTAREFAS.csv"

def limpar_valor(val):
    if pd.isna(val):
        return None
    return val

print("🚀 Iniciando migração inteligente com Mapeamento de Usuários...\n")

with engine.begin() as conn:
    
    # ==========================================
    # FASE 1: MAPEAMENTO INTELIGENTE DE USUÁRIOS
    # ==========================================
    print("👥 Construindo dicionário tradutor de usuários para evitar conflitos...")
    
    df_users = pd.read_csv(ARQUIVO_USUARIOS, encoding='latin1', sep=None, engine='python')
    df_users.columns = df_users.columns.str.replace('ï»¿', '', regex=False).str.replace('\ufeff', '', regex=False).str.strip()
    
    # 1. Pega os usuários que já estão no banco para comparar
    usuarios_banco = conn.execute(text("SELECT USUARIO_ID, EMAIL FROM tbUSUARIO")).fetchall()
    mapa_db_emails = {row[1].lower().strip(): row[0] for row in usuarios_banco if row[1]}

    mapa_ids_usuarios = {} # Dicionário Mágico: { ID_DA_PLANILHA : ID_DO_BANCO }
    usuarios_inseridos = 0
    
    for _, row in df_users.iterrows():
        u_id_csv = int(row["USUARIO_ID"])
        u_nome = str(row["NOME"]).strip()
        
        email_raw = row["EMAIL"]
        u_email = str(email_raw).strip().lower() if pd.notna(email_raw) else f"sem_email_{u_id_csv}@saavedra.com.br"
        u_login = u_email.split("@")[0]
        
        if u_email in mapa_db_emails:
            # O usuário já existe! Guardamos qual é o ID oficial dele no banco
            mapa_ids_usuarios[u_id_csv] = mapa_db_emails[u_email]
        else:
            # O usuário não existe. Inserimos e pegamos o novo ID gerado pelo banco
            res = conn.execute(text("""
                INSERT INTO tbUSUARIO (NOME, EMAIL, AD_LOGIN, PERFIL, NIVEL_ACESSO, ATIVO, SENHA_HASH)
                OUTPUT INSERTED.USUARIO_ID
                VALUES (:nome, :email, :login, 'Comum', 1, 1, 'migracao123')
            """), {"nome": u_nome, "email": u_email, "login": u_login})
            
            novo_id = res.fetchone()[0]
            mapa_ids_usuarios[u_id_csv] = novo_id
            mapa_db_emails[u_email] = novo_id # Atualiza o cache local
            usuarios_inseridos += 1
            
    print(f"   -> {usuarios_inseridos} novos usuários inseridos com sucesso.")
    print(f"   -> {len(mapa_ids_usuarios)} usuários foram perfeitamente mapeados!\n")

    # ==========================================
    # FASE 2: IMPORTAR TAREFAS E DIVIDIR O HISTÓRICO
    # ==========================================
    print("🎫 Importando Tarefas e traduzindo chaves estrangeiras...")
    
    df_tarefas = pd.read_csv(ARQUIVO_TAREFAS, encoding='latin1', sep=None, engine='python')
    df_tarefas.columns = df_tarefas.columns.str.replace('ï»¿', '', regex=False).str.replace('\ufeff', '', regex=False).str.strip()
    
    colunas_data = ["DATA_HORA", "DATA_CONCLUSAO", "DATA_ULTIMA_ATUALIZACAO", "DATA_LIMITE_SLA"]
    for col in colunas_data:
        if col in df_tarefas.columns:
            df_tarefas[col] = pd.to_datetime(df_tarefas[col], format='mixed', dayfirst=True, errors='coerce')

    inseridos_tarefas = 0
    inseridos_historico = 0

    for _, row in df_tarefas.iterrows():
        titulo = str(row['TITULO'])[:200]
        desc_completa = str(row['DESCRICAO'])
        
        prio_id = int(row['PRIORIDADE_ID']) if pd.notna(row['PRIORIDADE_ID']) else 4
        status_id = int(row['STATUS']) if pd.notna(row['STATUS']) else 1
        tipo_id = int(row['TIPO_ID']) if pd.notna(row['TIPO_ID']) else 1
        causa_id = int(row['CAUSA_RAIZ_ID']) if pd.notna(row['CAUSA_RAIZ_ID']) else None
        
        # --- AQUI ACONTECE A TRADUÇÃO DOS IDs ---
        tec_id_csv = int(row['USUARIO']) if pd.notna(row['USUARIO']) else None
        tec_id = mapa_ids_usuarios.get(tec_id_csv, None) if tec_id_csv else None

        solic_id_csv = int(row['SOLICITANTE_ID']) if pd.notna(row['SOLICITANTE_ID']) else None
        solic_id = mapa_ids_usuarios.get(solic_id_csv, None) if solic_id_csv else None
        # -----------------------------------------

        d_hora = limpar_valor(row['DATA_HORA'])
        d_conc = limpar_valor(row['DATA_CONCLUSAO'])
        d_upd = limpar_valor(row['DATA_ULTIMA_ATUALIZACAO'])
        d_sla = limpar_valor(row['DATA_LIMITE_SLA'])

        # Fatia o Histórico
        padrao = r'\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2})\] Atualização:'
        partes = re.split(padrao, desc_completa)
        
        desc_principal = partes[0].strip()
        if not desc_principal or desc_principal == 'nan':
            desc_principal = "Sem descrição inicial fornecida."

        resultado = conn.execute(text("""
            INSERT INTO tbTAREFAS (
                TITULO, DESCRICAO, PRIORIDADE_ID, TECNICO_ID, STATUS_ID,
                SOLICITANTE_ID, TIPO_ID, CAUSA_RAIZ_ID, DATA_HORA, DATA_CONCLUSAO,
                DATA_ULTIMA_ATUALIZACAO, DATA_LIMITE_SLA
            )
            OUTPUT INSERTED.TAREFA_ID
            VALUES (
                :titulo, :desc, :prio, :tec, :status, :solic, :tipo, :causa,
                :d_hora, :d_conc, :d_upd, :d_sla
            )
        """), {
            "titulo": titulo, "desc": desc_principal, "prio": prio_id, "tec": tec_id, 
            "status": status_id, "solic": solic_id, "tipo": tipo_id, "causa": causa_id,
            "d_hora": d_hora, "d_conc": d_conc, "d_upd": d_upd, "d_sla": d_sla
        })
        
        nova_tarefa_id = resultado.fetchone()[0]
        inseridos_tarefas += 1

        # Insere a primeira ação na linha do tempo
        conn.execute(text("""
            INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA)
            VALUES (:t_id, :u_id, 1, 'Abertura do Chamado (Importado)', :d_hora)
        """), {"t_id": nova_tarefa_id, "u_id": solic_id or 1, "d_hora": d_hora})

        # Insere os work notes na linha do tempo
        if len(partes) > 1:
            for i in range(1, len(partes), 2):
                data_str = partes[i]
                comentario = partes[i+1].strip()
                
                try:
                    data_hist = datetime.strptime(data_str, "%d/%m/%Y %H:%M")
                except:
                    data_hist = d_upd
                
                if comentario and comentario != 'nan':
                    conn.execute(text("""
                        INSERT INTO tbTAREFA_HISTORICO (TAREFA_ID, USUARIO_ID, STATUS_ID_NA_OCASIAO, COMENTARIO, DATA_HORA)
                        VALUES (:t_id, :u_id, :status, :coment, :d_hist)
                    """), {
                        "t_id": nova_tarefa_id,
                        "u_id": tec_id or 1, 
                        "status": status_id, 
                        "coment": comentario,
                        "d_hist": data_hist
                    })
                    inseridos_historico += 1

print(f"\n✅ Migração concluída com perfeição!")
print(f"🎫 Total de Chamados importados: {inseridos_tarefas}")
print(f"📜 Atualizações extraídas para a timeline ITIL: {inseridos_historico}")