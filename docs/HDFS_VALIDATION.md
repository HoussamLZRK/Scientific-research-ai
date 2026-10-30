# Validation HDFS - Scientific Research AI

Date de verification (UTC) : 2026-10-30 21:27:26

- Hadoop : 3.4.3 (Docker Compose)
- Architecture : 1 NameNode + 1 DataNode, replication 1
- Controle fsck : HEALTHY ; 7 fichiers et 7 blocs valides
- Comparaison SHA-256 locale / HDFS : 7/7 identiques

| Chemin HDFS | SHA-256 |
|---|---|
| `/scientific-research-ai/raw/crawler/publications_v2.jsonl` | `6c55a89898e3981bb07c0fa495ea26777d656a34937ea8d937c1e5221fa54aac` |
| `/scientific-research-ai/raw/crawler/publications_pmlr_v3.jsonl` | `b21958569dd8ff415eeb4f8f6334d454b22a27363348f1ca97464af046619525` |
| `/scientific-research-ai/processed/publications_multisource_v3.jsonl` | `f2cffb0791a9b0bee49f7e3df304dac8802c901bad87e6c441bbbd36ba7d541c` |
| `/scientific-research-ai/raw/sample_documents/acl_rag_retrievers_2024.pdf` | `23c24918d488485c1d1f4a4d718535addd2cf6dd848579ec96e3cbc4b3fde418` |
| `/scientific-research-ai/raw/sample_documents/pmlr_retrieval_models_2024.pdf` | `698e0591088e5aac70ac411707d36d1153e08ba6c73464f65b6dc130dc307693` |
| `/scientific-research-ai/raw/sample_documents/plos_llm_science_2024.pdf` | `d773d77f79c655dbd203f23f8b29ee29c2ae881e0ffc3c3573bc3da464ec3e72` |
| `/scientific-research-ai/raw/sample_documents/hal_wikidata_llm_2024.pdf` | `54b38739357a742a8b879933915e814d89d2b5ab00ea342a85edd8a06217f672` |

Ce rapport ne contient ni PDF ni JSONL. Le stockage fonctionne sur un seul ordinateur ; la replication 1 ne procure pas de redondance.
