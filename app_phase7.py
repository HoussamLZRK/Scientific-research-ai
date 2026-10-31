"""Scientific Research AI — Phase 7 demo UI.
Launch from the project root with python -m streamlit run app_phase7.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import streamlit_phase7_backend as core

st.set_page_config(page_title='Scientific Research AI | INPT', page_icon='◈', layout='wide',
                   initial_sidebar_state='expanded')

st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');
:root {color-scheme:dark}
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {background:#090f1c!important;color:#e9eef9!important}
[data-testid="stSidebar"] {background:#101a2c!important;border-right:1px solid #23314b!important}
[data-testid="stSidebar"] * {color:#dce6fa}
section.main > div {max-width:1470px;padding-top:1.55rem}
h1,h2,h3,[data-testid="stHeading"] {font-family:'Outfit',sans-serif!important;letter-spacing:-.028em}
h1 {font-weight:800!important}
p,li,label,button {font-family:'DM Sans',sans-serif}
[data-testid="stMetric"] {border-radius:18px;padding:16px 18px;background:linear-gradient(135deg,#142139,#17233a);border:1px solid #2b3b57}
[data-testid="stMetricLabel"] {color:#96aacc!important}
[data-testid="stMetricValue"] {color:#f3f7ff!important}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#31415e!important;border-radius:16px!important}
[data-testid="stChatMessage"] {background:#111e34;border:1px solid #2b3d58;border-radius:16px}
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {background-color:#111d31!important;border-color:#30425e!important;color:#ebf3ff!important}
.stButton > button[kind="primary"] {background:linear-gradient(110deg,#6178eb,#3689cf)!important;border:0!important;font-weight:700;color:white!important;border-radius:11px}
.stButton > button {border-radius:10px!important}
[data-testid="stTabs"] [role="tab"] {font-weight:600}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {background:#121e32!important;color:#ebf3ff!important}
small, .quiet {color:#8aa2c3}
.hero {background:radial-gradient(circle at 90% 15%,rgba(66,140,222,.22),transparent 30%),linear-gradient(120deg,#172940 0%,#122039 57%,#15253e 100%);border:1px solid #314867;border-radius:22px;padding:29px 32px;margin-bottom:22px}
.eyebrow {font-size:.72rem;color:#89bfff;text-transform:uppercase;letter-spacing:.19em;font-weight:800}
.hero h1 {font-size:2.45rem!important;margin:.2em 0 .25em;color:#f0f5ff}
.hero p {font-size:.99rem;color:#b9c9e3;max-width:1000px;margin:0}
.section-eyebrow {font-size:.76rem;font-weight:700;letter-spacing:.08em;color:#8fa5c7;text-transform:uppercase}
.tip {background:#122136;padding:14px 18px;border-radius:14px;border-left:3px solid #679ef3;color:#c6d5ef;font-size:.88rem;margin:9px 0 18px}
.source-count {font-size:.76rem;color:#a2b7d6;letter-spacing:.03em}
.brand {border-radius:14px;background:#152943;padding:14px 16px;border:1px solid #294464;font-weight:800;color:#f4f7ff}
[data-testid="stAppDeployButton"] {display:none}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def read_corpus(path: str, stamp: int):
    return core.lexical.load_chunks(Path(path))


@st.cache_data(show_spinner=False)
def read_report(path: str, stamp: int):
    return core.load_optional_report(Path(path))


def get_corpus():
    path = core.CORPUS
    return read_corpus(str(path), path.stat().st_mtime_ns)


def get_report(path):
    return read_report(str(path), path.stat().st_mtime_ns) if path.is_file() else None


def hero(section: str, title: str, subtitle: str):
    st.markdown(f'<div class="hero"><div class="eyebrow">{section}</div><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


def report_download(report: dict, file_name: str):
    st.download_button('Télécharger les résultats (JSON)',
            json.dumps(report, indent=2, ensure_ascii=False),
            file_name=file_name, mime='application/json',use_container_width=True)


def source_list(result):
    retrieved=result.get('retrieved') or []
    if not retrieved:
        st.warning('Aucun passage retrouvé pour cette question et ces filtres.')
        return
    st.dataframe(core.source_rows(result),use_container_width=True,hide_index=True)
    st.markdown('##### Lecture des passages')
    for i,row in enumerate(retrieved,1):
        label=f'[{i}] {row["document_id"]} · page {row["page_number"]} · {row["chunk_id"]}'
        with st.expander(label,expanded=i==1):
            if row.get('graph_entity_names'):
                st.caption('Entités mentionnées selon Neo4j : '+', '.join(row['graph_entity_names']))
            st.write(row['text'])
            st.caption('Référence document / page / chunk ; ne constitue pas une validation automatique de la réponse.')


def sidebar():
    with st.sidebar:
        st.markdown('<div class="brand">◈ &nbsp; SCIENTIFIC RESEARCH AI</div>',unsafe_allow_html=True)
        st.caption('INPT  ·  Big Data + IA  ·  Démonstrateur local')
        st.divider()
        page=st.radio('Navigation',[
            'Vue d’ensemble','Assistant scientifique','Graph Analytics','Explorateur de corpus','Évaluation : protocole'],
            label_visibility='collapsed')
        st.divider()
        st.markdown('**Services locaux**')
        status_ollama=core.check_ollama()
        st.write('🟢 Ollama connecté' if status_ollama['available'] else '🔴 Ollama inaccessible')
        status_faiss=core.faiss_status()
        st.write('🟢 Index FAISS trouvé' if status_faiss['available'] else '🔴 Index FAISS absent')
        st.caption('Neo4j : vérifier la connexion dans GraphRAG / Graph Analytics.')
        with st.expander('Connexion Neo4j',expanded=False):
            st.text_input('URI Bolt',value=core.NEO4J_URI,key='neo4j_uri')
            st.text_input('Utilisateur',value='neo4j',key='neo4j_user',disabled=True)
            st.text_input('Mot de passe Neo4j',type='password',key='neo4j_pwd',
                          help='Conservé uniquement dans la session Streamlit. Ne sera pas enregistré dans le rapport.')
            if os.environ.get('NEO4J_PASSWORD'):
                st.caption('Variable NEO4J_PASSWORD disponible : elle sera utilisée si le champ est vide.')
        st.divider()
        st.caption('Les PDF et le graphe sont lus sans modification. Les relations d’entités sont des mentions lexicales.')
        return page


def password():
    return st.session_state.get('neo4j_pwd') or os.environ.get('NEO4J_PASSWORD') or ''


def dashboard(chunks):
    hero('01  /  VUE D’ENSEMBLE', 'Votre laboratoire de recherche scientifique',
         'De l’extraction de publications à la recherche augmentée par graphe. Les indicateurs affichés proviennent du corpus et des rapports générés par les phases précédentes.')
    overview=core.corpus_overview(chunks)
    structural=get_report(core.STRUCTURAL_REPORT)
    scientific=get_report(core.SCIENTIFIC_REPORT)
    s=(structural or {}).get('summary',{})
    e=(scientific or {}).get('summary',{})
    cols=st.columns(4)
    cols[0].metric('Publications collectées',str(s.get('node_counts',{}).get('SRAIPublication','—')))
    cols[1].metric('Documents PDF',str(overview['documents']))
    cols[2].metric('Chunks indexables',str(overview['chunks']))
    cols[3].metric('Entités lexicales uniques',str(e.get('unique_entities','—')))
    st.caption('Le nombre de publications vient du rapport structurel ; les PDF ne sont pas automatiquement liés aux publications du crawler.')
    left,right=st.columns([1.35,1],gap='large')
    with left:
        st.subheader('Couverture du corpus')
        st.bar_chart(overview['document_rows'],x='Document',y='Chunks',
                     x_label='Document',y_label='Chunks')
        st.dataframe(overview['document_rows'],hide_index=True,use_container_width=True)
    with right:
        st.subheader('État des analyses')
        if structural:
            c1,c2=st.columns(2)
            c1.metric('Nœuds structurels',s.get('total_nodes','—'))
            c2.metric('Relations structurelles',s.get('total_relations','—'))
            c3,c4=st.columns(2)
            c3.metric('Composantes connexes',s.get('components','—'))
            c4.metric('Plus grande composante',s.get('largest_component_nodes','—'))
        else:
            st.info('Rapport Graph Analytics structurel non trouvé : `data/reports/graph_analytics_report.json`')
        if scientific:
            st.metric('Mentions lexicales extraites',e.get('entity_mentions','—'))
            st.caption('Ces mentions ne sont pas des relations scientifiques vérifiées.')
        else:
            st.info('Rapport scientifique 5B non trouvé : `data/reports/graph_analytics_scientific_phase5b.json`')
    st.markdown('<div class="tip">Corpus exploratoire de 4 PDF et 263 chunks ; l’enrichissement Neo4j ne couvre actuellement qu’une petite partie des passages. Cette limitation doit être mentionnée lors de la démonstration.</div>',unsafe_allow_html=True)
    st.subheader('Chaîne de traitement')
    st.code('Crawler → HDFS → Spark ETL → Neo4j / Graph Analytics\nPDF → Chunking → BM25 + embeddings FAISS → RRF → GraphRAG → Qwen2.5:7b',language='text')


def assistant(chunks):
    hero('02  /  ASSISTANT SCIENTIFIQUE', 'Interroger les publications',
         'Comparez la recherche lexicale, hybride et augmentée par graphe sur le même corpus. Chaque réponse présente ses passages sources.')
    docs=sorted({c['document_id'] for c in chunks})
    with st.form('ask_form',clear_on_submit=False):
        question=st.text_area('Votre question scientifique',
            value='How does BGM improve retrieval compared with GTR?',height=92,
            help='Les articles étant en anglais, commencez par poser les questions en anglais.')
        row=st.columns([1.6,1.1,1.1,1.3])
        mode=row[0].selectbox('Méthode',core.MODES,index=2)
        top_k=row[1].selectbox('Passages finaux',list(range(1,9)),index=2)
        candidate_options=list(range(max(3,top_k),9))
        candidates_k=row[2].selectbox('Candidats/méthode',candidate_options,
                                     index=candidate_options.index(max(6,candidate_options[0])) if max(6,candidate_options[0]) in candidate_options else 0,
                                     disabled=mode=='RAG BM25')
        doc=row[3].selectbox('Document', ['Tous les documents']+docs)
        cols=st.columns([1.1,1.15,2.2])
        gen=cols[0].checkbox('Générer une réponse',value=True)
        rerank=cols[1].checkbox('Activer le reranking',value=False,disabled=mode=='RAG BM25')
        cols[2].caption('Le reranking utilise Qwen2.5:7b et peut ralentir la génération.')
        submitted=st.form_submit_button('Lancer la recherche',type='primary',use_container_width=True)
    if mode=='GraphRAG Neo4j' and not password():
        st.info('GraphRAG nécessite le mot de passe Neo4j dans la barre latérale, rubrique « Connexion Neo4j ».')
    if submitted:
        try:
            with st.spinner('Recherche en cours…' + (' génération de la réponse avec Ollama.' if gen else '')):
                result=core.run_query(mode=mode,question=question,top_k=top_k,
                     candidates_k=candidates_k,use_rerank=rerank and mode!='RAG BM25',generate=gen,
                     document_id=None if doc=='Tous les documents' else doc,
                     neo4j_password=password(),neo4j_uri=st.session_state.get('neo4j_uri') or core.NEO4J_URI)
            st.session_state['phase7_result']=result
        except (ValueError,RuntimeError,OSError,KeyError,ImportError) as exc:
            st.error('Recherche impossible : '+str(exc))
        except Exception as exc:
            st.error(f'Erreur du service {type(exc).__name__} : {str(exc)}')
    result=st.session_state.get('phase7_result')
    if not result:
        st.markdown('<div class="tip">Choisissez un mode puis lancez la recherche. Les résultats n’apparaissent qu’après exécution effective, jamais sous forme de réponses préenregistrées.</div>',unsafe_allow_html=True)
        return
    st.divider()
    st.markdown('### Résultat de la dernière exécution')
    a,b,c=st.columns(3)
    a.metric('Méthode',result.get('ui_mode','—'))
    b.metric('Passages finaux',len(result.get('retrieved') or []))
    c.metric('Durée totale',f"{result.get('ui_elapsed_seconds','—')} s")
    st.caption('Question : '+result.get('question','')+' · '+result.get('ui_generated_at_utc',''))
    answer=result.get('generation')
    if answer:
        with st.chat_message('assistant'):
            st.markdown(answer.get('answer') or 'Aucune réponse fournie.')
        if answer.get('citation_warning'):
            st.warning('La réponse n’inclut aucune citation explicite. Vérifiez le contenu avant de la présenter.')
        if answer.get('citations_used'):
            st.caption('Numéros de sources cités : '+', '.join(map(str,answer['citations_used'])))
    else:
        st.info('Recherche seulement : aucune réponse n’a été générée lors de cette exécution.')
    if result.get('graph'):
        g=result['graph']
        st.subheader('Apport du graphe Neo4j')
        x,y,z=st.columns(3)
        x.metric('Entités dans la question',g.get('matched_entity_count',0))
        y.metric('Chunks liés au graphe',g.get('eligible_graph_chunks',0))
        z.metric('Nouveaux chunks sélectionnés',g.get('novel_chunk_count',0))
        if g.get('question_entities'):
            st.caption('Entités reconnues : '+', '.join(r['name'] for r in g['question_entities']))
        if g.get('fallback_reason'):
            st.warning('Repli vers la recherche hybride : '+g['fallback_reason'])
        st.caption('Les liens Neo4j sont des mentions lexicales uniquement. Un nouveau chunk ne garantit pas une meilleure réponse.')
    st.subheader('Passages utilisés pour répondre')
    source_list(result)
    report_download(result,'srai_phase7_last_query.json')


def analytics(chunks):
    hero('03  /  GRAPH ANALYTICS', 'Comprendre notre graphe',
         'Indicateurs de structure et co-mentions scientifiques exploratoires. Cette analyse ne prétend pas calculer de vraies collaborations scientifiques ni de citations entre articles.')
    structural=get_report(core.STRUCTURAL_REPORT)
    scientific=get_report(core.SCIENTIFIC_REPORT)
    tabs=st.tabs(['Topologie structurelle','Entités & co-mentions','Sous-graphe Neo4j'])
    with tabs[0]:
        if not structural:
            st.warning('Rapport structurel absent. Exécutez `scripts/graph_analytics_phase5.py` puis actualisez cette page.')
        else:
            data=structural['summary']
            cols=st.columns(4)
            for metric,value,c in zip(('Nœuds','Relations','Composantes','Isolés'),
                   (data.get('total_nodes'),data.get('total_relations'),data.get('components'),data.get('isolated_nodes')),cols):
                c.metric(metric,value if value is not None else '—')
            st.caption(data.get('interpretation','Topologie documentaire uniquement.'))
            st.markdown('#### Types de nœuds')
            st.bar_chart([{'Type':k,'Nombre':v} for k,v in data.get('node_counts',{}).items()],
                         x='Type',y='Nombre',x_label='Type de nœud',y_label='Nombre')
            st.markdown('#### Documents')
            if structural.get('documents'):
                st.dataframe(structural['documents'],hide_index=True,use_container_width=True)
            st.markdown('#### Publications du crawler')
            if structural.get('publications'):
                st.dataframe(structural['publications'],hide_index=True,use_container_width=True)
    with tabs[1]:
        if not scientific:
            st.warning('Rapport Phase 5B absent. Exécutez `scripts/graph_analytics_scientific_phase5b.py --analyze` puis actualisez.')
        else:
            s=scientific.get('summary',{})
            cols=st.columns(4)
            for c,name,value in zip(cols,('Entités uniques','Mentions','Co-mentions','Chunks enrichis'),
                 (s.get('unique_entities'),s.get('entity_mentions'),s.get('co_mention_pairs'),s.get('input_chunks_with_entities'))):
                c.metric(name,value if value is not None else '—')
            ranked=scientific.get('entity_ranking') or []
            if ranked:
                st.markdown('#### Entités les plus mentionnées')
                st.bar_chart([{'Entité':r['entity'],'Chunks':r['chunks_mentioning']} for r in ranked[:12]],
                             x='Entité',y='Chunks',y_label='Chunks')
                st.dataframe(ranked,hide_index=True,use_container_width=True)
            with st.expander('Co-mentions dans les mêmes chunks'):
                st.dataframe(scientific.get('co_mentions',[]),use_container_width=True,hide_index=True)
            st.warning('Mention et co-mention ≠ relation scientifique vérifiée. Les types d’entités peuvent comporter des erreurs d’extraction.')
    with tabs[2]:
        docs=sorted({c['document_id'] for c in chunks})
        doc=st.selectbox('Choisir un document',docs,key='graph_document')
        doc_pages=sorted({c['page_number'] for c in chunks if c['document_id']==doc})
        options=['Toutes les pages']+doc_pages
        default_page=7 if 7 in doc_pages else (doc_pages[0] if doc_pages else 'Toutes les pages')
        psel=st.selectbox('Page à visualiser',options,index=options.index(default_page))
        cap=st.slider('Nombre de chunks à afficher',3,12,8)
        st.caption('Vue issue des vraies arêtes HAS_CHUNK et MENTIONS_ENTITY, jamais d’arêtes inventées.')
        if st.button('Charger le sous-graphe depuis Neo4j',use_container_width=True):
            if not password():
                st.error('Renseignez le mot de passe Neo4j dans la barre latérale.')
            else:
                try:
                    with core.graph.neo4j_driver(st.session_state.get('neo4j_uri') or core.NEO4J_URI,password()) as driver:
                        nodes,edges=core.graph_preview_rows(driver,doc,cap,None if psel=='Toutes les pages' else psel)
                    st.session_state['subgraph']={'document_id':doc,'chunks':nodes,'mentions':edges}
                except Exception as exc:
                    st.error(f'Lecture Neo4j impossible : {type(exc).__name__} : {str(exc)}')
        g=st.session_state.get('subgraph')
        if g:
            st.caption(f"Dernier graphe chargé : {g['document_id']} · {len(g['chunks'])} chunks · {len(g['mentions'])} liens d’entités")
            st.graphviz_chart(core.make_dot(g['document_id'],g['chunks'],g['mentions']),use_container_width=True)
            if not g['mentions']:
                st.info('Aucune mention d’entité pour les chunks affichés. Ce n’est pas une erreur : seule une partie du corpus est enrichie.')
        else:
            st.info('Chargez un sous-graphe pour afficher les vrais nœuds et relations.')


def explorer(chunks):
    hero('04  /  CORPUS SCIENTIFIQUE', 'Explorer les preuves documentaires',
         'Consultez les passages réellement extraits des PDF et leurs identifiants. Les données affichées sont locales, sans génération LLM.')
    docs=sorted({c['document_id'] for c in chunks})
    a,b=st.columns([1.2,2.4])
    did=a.selectbox('Document',docs)
    query=b.text_input('Filtre textuel facultatif',placeholder='BGM, entity typing, retrieval…')
    relevant=[c for c in chunks if c['document_id']==did]
    pages=sorted({c['page_number'] for c in relevant})
    selected_pages=st.multiselect('Pages',pages,default=[],help='Laissez vide pour toutes les pages.')
    if selected_pages:
        relevant=[c for c in relevant if c['page_number'] in selected_pages]
    if query.strip():
        relevant=[c for c in relevant if query.casefold() in c['text'].casefold()]
    st.caption(f'{len(relevant)} passages correspondant aux filtres')
    display=relevant[:100]
    for row in display:
        with st.expander(f"Page {row['page_number']} · {row['chunk_id']}"):
            st.write(row['text'])
    if len(relevant)>100:
        st.warning('Affichage limité aux 100 premiers passages. Affinez les filtres.')


def evaluation_info():
    hero('05  /  MÉTHODOLOGIE', 'Évaluer avant de conclure',
         'Cette page définit le protocole de comparaison. Elle ne présente aucune mesure inventée : les évaluations multi-questions seront exécutées en Phase 8.')
    st.subheader('Comparaison expérimentale prévue')
    st.dataframe([
        {'Variante':'BM25','Recherche':'Lexicale','Graphe':'Non','LLM':'Qwen2.5:7b'},
        {'Variante':'Hybride','Recherche':'BM25 + FAISS + RRF','Graphe':'Non','LLM':'Qwen2.5:7b'},
        {'Variante':'GraphRAG','Recherche':'BM25 + FAISS + RRF','Graphe':'Neo4j (mentions)','LLM':'Qwen2.5:7b'},
    ],hide_index=True,use_container_width=True)
    st.markdown('''**Protocole :** mêmes questions, même corpus, même modèle génératif, même top-k et mêmes paramètres de reranking. Vérifier manuellement la pertinence et l’ancrage de chaque réponse dans les PDF.

**Mesures recommandées :** Recall@k ou Precision@k sur un jeu de passages pertinents annotés, fidélité des affirmations aux sources, taux de réponses insuffisantes, latence réelle et couverture du graphe.

**Limites actuelles :** 4 PDF, 263 chunks, enrichissement lexical limité ; les résultats ne sont pas généralisables à toute la littérature scientifique.''')
    st.info('Phase 8 : constitution d’un benchmark annoté, exécution des trois méthodes et comparaison chiffrée. Pas de score affiché tant qu’il n’a pas été mesuré.')


def main():
    page=sidebar()
    try:
        chunks=get_corpus()
    except (OSError,ValueError) as exc:
        hero('CONFIGURATION', 'Corpus introuvable', 'Vérifiez l’extraction PDF et le chemin des chunks.')
        st.error(str(exc))
        st.code('data/processed/chunks/pdf_chunks.jsonl',language='text')
        st.stop()
    if page=='Vue d’ensemble': dashboard(chunks)
    elif page=='Assistant scientifique': assistant(chunks)
    elif page=='Graph Analytics': analytics(chunks)
    elif page=='Explorateur de corpus': explorer(chunks)
    else: evaluation_info()
    st.divider()
    st.caption('Scientific Research AI · INPT · Données de recherche exploratoires · Réponses générées à vérifier dans leurs sources')


if __name__=='__main__':
    main()
