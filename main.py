import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# --- LÓGICA DE CARREGAMENTO DE SEGREDOS CORRIGIDA (FINAL) ---

# 1. Carrega o .env (sempre)
load_dotenv() 

# Tenta ler do .env (SUPABASE_URL terá um valor ou será None)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if SUPABASE_URL:
    # Caso 1: Rodando localmente, chaves encontradas no .env.
    # st.info("MODO LOCAL: Carregando chaves do arquivo .env")
    pass 

elif not SUPABASE_URL and "supabase" in st.secrets:
    # Caso 2: Rodando no Streamlit Cloud (chaves do .env estão vazias, mas st.secrets está preenchido)
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    # st.info("MODO DEPLOY: Carregando chaves do st.secrets")

else:
    # Caso 3: Falha total (não achou em lugar nenhum)
    st.error("ERRO CRÍTICO: Chaves do Supabase não encontradas. Verifique o arquivo .env (local) ou a configuração de segredos do Streamlit Cloud.")
    st.stop() 

# Cria o cliente Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


try:
    response = supabase.table("cards").select("titulo").execute()
    titulos = [item['titulo'] for item in response.data]
except Exception as e:
    st.error(f"Erro ao carregar títulos dos cards: {e}")
    titulos = []


def texto_de_ajuda():
    return  """
    - **Briefing incompleto**: Material de referência estava incompleto ou pouco claro  
    - **Execução fora do direcionamento**: Redator não seguiu corretamente o briefing ou roteiro  
    - **Tom ou linguagem inadequada**: Texto fora do tom de voz da marca, linguagem genérica ou inadequada  
    - **Alteração de rota pelo cliente**: Cliente mudou o pedido após entrega, mesmo com briefing validado  
    - **Solicitação estética (subjetiva)**: Mudança de palavras ou estilo por preferência subjetiva do cliente ou CS  
    - **Erro técnico de escrita**: Erros gramaticais, ortográficos ou de digitação  
    - **Erro de informação técnica**: Informações incorretas sobre produto, processo ou tema abordado  
    - **Ajuste por atualização de informações**: Mudança de contexto após entrega: campanha pausada, dados atualizados etc.
    """


def adicionar_refacao_callback(conteudo_id, count_atual):
    st.session_state.refacao_counts[conteudo_id] = count_atual + 1



def sincronizar_dados(card_id):
    response_refacoes = supabase.table("cards_refacao").select("*").eq("id_trello_card", card_id).execute()

    if response_refacoes.data:
        st.session_state.tem_card_refacao_data = response_refacoes.data
        st.session_state.refacao_counts = {}
        for r in st.session_state.tem_card_refacao_data:
            cont_num = r['numero_conteudo']
            ref_num = r['numero_refacao']
            current_max = st.session_state.refacao_counts.get(cont_num, 0)
            st.session_state.refacao_counts[cont_num] = max(current_max, ref_num)
    else:
        st.session_state.tem_card_refacao_data = []
        st.session_state.refacao_counts = {}



def manipular_exclusao(card_id, cont_num, ref_num, existe_no_banco):

    if existe_no_banco:
        try:
            supabase.table("cards_refacao").delete().match({
                "id_trello_card": card_id,
                "numero_conteudo": cont_num,
                "numero_refacao": ref_num
            }).execute()
            st.success(f"Refação {ref_num} do conteúdo {cont_num} excluída do banco.")
            
        except Exception as e:
            st.error(f"Erro ao excluir a refação do banco: {e}")

    if st.session_state.refacao_counts.get(cont_num, 0) > 1:
        st.session_state.refacao_counts[cont_num] -= 1
    elif st.session_state.refacao_counts.get(cont_num, 0) == 1:
        st.session_state.refacao_counts[cont_num] = 1 
    
    keys_to_delete = [
        f'tipo-{card_id}-{cont_num}-{ref_num}', f'motivo-{card_id}-{cont_num}-{ref_num}',
        f'time-{card_id}-{cont_num}-{ref_num}', f'cliente-{card_id}-{cont_num}-{ref_num}',
        f'placeholder-{card_id}-{cont_num}-{ref_num}'
    ]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    sincronizar_dados(card_id)




def main():
    st.sidebar.markdown("## Refação")
    time_responsavel_sessao = st.sidebar.selectbox('Time', ('Criação', 'Redação'), key='time_sessao_atual') 
    st.markdown(f'## Refação {time_responsavel_sessao}')

    dados_para_salvar = [] 
    id_card = None 
    tem_card_refacao_data = []
    dados_para_atualizar = []
    dados_para_inserir = []



    if 'refacao_counts' not in st.session_state:
        st.session_state.refacao_counts = {}
    
    if 'current_card_id' not in st.session_state:
        st.session_state.current_card_id = None

    if 'tem_card_refacao_data' not in st.session_state:
        st.session_state.tem_card_refacao_data = []

    with st.container():
        st.markdown('### Dados da Refação')


        nome_card_refacao = st.text_input(
            'Nome card:', 
            key='nome_card_selecionado'
        )

      
        if nome_card_refacao:   
            if nome_card_refacao not in titulos:
                st.warning("O card não foi encontrado")
                st.session_state.current_card_id = None 
            else:
                response_id = supabase.table("cards").select("trello_card_id").eq("titulo", nome_card_refacao).execute()
                if response_id.data:
                    id_card = response_id.data[0]["trello_card_id"]

                    if st.session_state.current_card_id != id_card:
                        st.session_state.current_card_id = id_card
                        st.session_state.refacao_counts = {}
                        st.session_state.tem_card_refacao_data = []
                        
                        response_refacoes = supabase.table("cards_refacao").select("*").eq("id_trello_card", id_card).execute()
                        
                        if response_refacoes.data:
                            st.session_state.tem_card_refacao_data = response_refacoes.data
                            st.info(f"{len(st.session_state.tem_card_refacao_data)} registros de refação encontrados.")
                            
                            for r in st.session_state.tem_card_refacao_data:
                                cont_num = r['numero_conteudo']
                                ref_num = r['numero_refacao']
                                current_max = st.session_state.refacao_counts.get(cont_num, 0)
                                st.session_state.refacao_counts[cont_num] = max(current_max, ref_num)
                        else:
                            st.info("Card encontrado, nenhuma refação registrada.")
                    
                    st.success("Card carregado.")
                else:
                    st.error("Card não encontrado no banco.")
                    st.session_state.current_card_id = None
        
      
        if id_card:
            
            conteudo_selecionado = st.slider(
                'Selecione o Conteúdo:', 1, 20, 1,
                key=f'slider-conteudo-{id_card}' 
            )
            st.markdown(f"### Refações para o {conteudo_selecionado}° Conteúdo")

       
            num_refacoes = st.session_state.refacao_counts.get(conteudo_selecionado, 1)


            st.button(
                f"Adicionar Refação",
                key = f'ADD_GLOBAL_{id_card}_{conteudo_selecionado}',
                on_click=adicionar_refacao_callback,
                args=(conteudo_selecionado, num_refacoes)
            )

            st.divider()


            for ref_num in range(1, num_refacoes + 1):
                
                dados_existentes = next(
                    (r for r in st.session_state.tem_card_refacao_data 
                     if r.get("numero_conteudo") == conteudo_selecionado and r.get("numero_refacao") == ref_num), 
                    None 
                )

                tag_time = ""
                time_da_refacao = None

                if dados_existentes and dados_existentes.get("time_responsavel"):
                    time_da_refacao = dados_existentes['time_responsavel']

                else:
                    time_da_refacao = time_responsavel_sessao

                if time_da_refacao == "Criação":
                    tag_time = "🎨 [Criação]"
                elif time_da_refacao == "Redação":
                    tag_time = "✍️ [Redação]"

                with st.expander(f"#### {ref_num}ª Refação {tag_time}", expanded=True):
                    
                    col1, col2, col3 = st.columns(3) 
                    

                    with col1:
                        opcoes_tipo = [' ', 'Externa', 'Interna']
                        key_tipo = f'tipo-{id_card}-{conteudo_selecionado}-{ref_num}'
                        valor_atual = st.session_state.get(key_tipo, None)
                        
                        idx_tipo = 0
                        if valor_atual:
                            try: idx_tipo = opcoes_tipo.index(valor_atual)
                            except ValueError: idx_tipo = 0
                        elif dados_existentes and dados_existentes.get("tipo_refacao") in opcoes_tipo:
                            idx_tipo = opcoes_tipo.index(dados_existentes["tipo_refacao"])
                        
                        st.selectbox(
                            'Tipo Refação', opcoes_tipo,
                            key=key_tipo, 
                            index=idx_tipo
                        )
                    
                  
                    with col2:
                        opcoes_motivo = [
                            " ", "Briefing incompleto", "Execução fora do direcionamento", 
                            "Erro técnico (para alterações de erro interno, ex: logo errada, cor errada)", 
                            "Alteração estética (solicitada pelo cliente)", 
                            "Alteração estética (solicitada pelo time)", 
                            "Ajuste por atualização de informações"
                        ]
                        
                        key_motivo = f'motivo-{id_card}-{conteudo_selecionado}-{ref_num}'
                        valor_motivo_atual = st.session_state.get(key_motivo, None)
                        
                        idx_motivo = 0
                        if valor_motivo_atual:
                            try: idx_motivo = opcoes_motivo.index(valor_motivo_atual.strip())
                            except ValueError: idx_motivo = 0
                        elif dados_existentes and dados_existentes.get("motivo_refacao"):
                            try: idx_motivo = opcoes_motivo.index(dados_existentes["motivo_refacao"].strip())
                            except ValueError: idx_motivo = 0
                        
                        motivo_refacao = st.selectbox(
                            'Motivo Refação', opcoes_motivo, 
                            key=key_motivo,
                            index=idx_motivo
                        )
                       

                    with col3:
                        time_solicitou_refacao = None
                        cliente_solicitou_refacao = None

                        key_da_col1 = f'tipo-{id_card}-{conteudo_selecionado}-{ref_num}'
                        valor_real_da_col1 = st.session_state.get(key_da_col1, ' ') 
                    
                        if valor_real_da_col1 == 'Interna': 
                            time_opcoes = [' ', 'Refação', 'Criação', 'Automação', 'Tech', 'Performance', 'Comunicação']
                            key_time = f'time-{id_card}-{conteudo_selecionado}-{ref_num}'
                            valor_time = st.session_state.get(key_time, None)

                            idx_time = 0
                            if valor_time:
                                try: idx_time = time_opcoes.index(valor_time)
                                except ValueError: idx_time = 0
                            elif dados_existentes and dados_existentes.get("time_solicitou_refacao") in time_opcoes:
                                idx_time = time_opcoes.index(dados_existentes["time_solicitou_refacao"])

                            time_solicitou_refacao = st.selectbox(
                                'Time que solicitou:', time_opcoes, 
                                key=key_time,
                                index=idx_time
                            )
                        elif valor_real_da_col1 == 'Externa':
                            cliente_opcoes = [' ', 'Hospitalar', 'BR Consórcios', 'SnowDog', 'Arnaldos']
                            key_cliente = f'cliente-{id_card}-{conteudo_selecionado}-{ref_num}'
                            valor_cliente = st.session_state.get(key_cliente, None)

                            idx_cliente = 0
                            if valor_cliente:
                                try: idx_cliente = cliente_opcoes.index(valor_cliente)
                                except ValueError: idx_cliente = 0
                            elif dados_existentes and dados_existentes.get("cliente_solicitou_refacao") in cliente_opcoes:
                                idx_cliente = cliente_opcoes.index(dados_existentes["cliente_solicitou_refacao"])

                            cliente_solicitou_refacao = st.selectbox(
                                'Cliente que solicitou:', cliente_opcoes, 
                                key=key_cliente,
                                index=idx_cliente
                            )
                        else:
                            st.selectbox(
                                'Time/Cliente',
                                ['Selecione um Tipo de Refação'],
                                disabled=True,
                                key=f'placeholder-{id_card}-{conteudo_selecionado}-{ref_num}'
                            )
        
                    
                    _, col_btn_apagar = st.columns([4, 1]) 
                    
                    with col_btn_apagar:
                        st.button(
                            "Excluir",
                            key=f'DELETE_GLOBAL-{id_card}-{conteudo_selecionado}-{ref_num}', 

                            on_click=manipular_exclusao,
                            args=(id_card, conteudo_selecionado, ref_num, bool(dados_existentes)), 
                            type="primary"
                        )

                    
                    dados_coletados = {
                        "id_trello_card": id_card,
                        "titulo": nome_card_refacao,
                        "numero_conteudo": conteudo_selecionado,
                        "numero_refacao": ref_num,  
                        "tipo_refacao": valor_real_da_col1, 
                        "motivo_refacao": motivo_refacao,
                        "time_solicitou_refacao": time_solicitou_refacao,
                        "cliente_solicitou_refacao": cliente_solicitou_refacao,
                        "time_responsavel": time_da_refacao
                    }
                    if dados_existentes:
                        dados_para_atualizar.append(dados_coletados)
                    else:
                        dados_para_inserir.append(dados_coletados)

       
        pode_salvar = bool(dados_para_atualizar or dados_para_inserir)
        
        if pode_salvar:
            if st.button(f"Salvar no Banco de Dados", key=f'salvar-{id_card}'):
                try:
                    
                    if dados_para_atualizar:
                        response_update = supabase.table("cards_refacao").upsert(
                            dados_para_atualizar, 
                            on_conflict="id_trello_card,numero_conteudo,numero_refacao" 
                        ).execute()
                        if hasattr(response_update, 'error') and response_update.error:
                            raise Exception(f"Erro ao ATUALIZAR: {response_update.error['message']}")

                  
                    if dados_para_inserir:
                        response_insert = supabase.table("cards_refacao").insert(
                            dados_para_inserir
                        ).execute()
                        if hasattr(response_insert, 'error') and response_insert.error:
                            raise Exception(f"Erro ao INSERIR: {response_insert.error['message']}")


                    st.success("Dados enviados com sucesso!")
                    sincronizar_dados(id_card)
                    st.rerun()

                except Exception as e:
                    if "duplicate key value violates unique constraint" in str(e):
                        st.warning("Ops! Alguém salvou uma refação ao mesmo tempo. Estamos atualizando sua tela. Verifique seus dados e salve novamente.")
                        sincronizar_dados(id_card)
                        st.rerun()
                    else:
                        st.error(f"Ocorreu um erro na operação com o banco: {e}")



            
if __name__ == "__main__":
    main()  