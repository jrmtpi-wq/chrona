# Varredura do balanceamento automático — 07/10/2026

O balanceamento automático existe e o plano original foi localizado no histórico do repositório. A implementação ainda não cumpre integralmente esse plano: permite sobrecarga da mesma pessoa, ultrapassa a distância de apoio e perde atribuições e divisões ao salvar/reabrir. A geração atual deve ser tratada como sugestão incompleta, pois o retorno `ok: true` não comprova que o resultado seja executável no ciclo informado.

A varredura inicial não alterou o código funcional nem os dados reais. As reproduções utilizaram SQLite temporário e navegador local. Após a autorização do proprietário, as correções descritas abaixo foram implementadas. Não houve montagem nem substituição de balanceamento real durante os testes.

## Correção implementada após autorização

- Duas operadoras principais por time, com vínculo principal único; apoios separados até dois times antes ou depois.
- Carga máxima global de ciclo + 1 minuto por pessoa (16 para ciclo de 15), incluindo todos os apoios. Os tempos são utilizados como cadastrados, sem reaplicar os 18%.
- Geração sequencial com divisão entre pessoas, seleção apenas de operadoras ativas da fábrica/grupo e respeito às quantidades configuradas. Compatibilidade de equipamento usa o tempo padrão da operação e emite aviso de treinamento.
- Quando a heurística não encontra cobertura completa, informa o impedimento e preserva a montagem atual. Isso não prova matematicamente que outra composição seja impossível.
- Atribuições do automático alimentam o mesmo cálculo global e a impressão usados pela montagem manual.
- Gravação validada no servidor: dupla, vínculo, distância, carga, quantidades, cobertura e ordem do roteiro. Um envio inválido não substitui o registro anterior.
- Montagem integral preservada em `balanceamento.montagem_json`, com partes, índices do roteiro, tempos aplicados, turno e grupo. A migração adiciona somente essa coluna, em SQLite e PostgreSQL. Registros antigos permanecem acessíveis pelo carregamento anterior; devem ser regenerados para obter as atribuições que o código antigo não gravou.
- Operações repetidas distinguem os itens do roteiro; `sequencia_op.time_numero` registra o primeiro time, enquanto as divisões completas ficam na montagem salva e na exportação.
- Configuração sincroniza duas operadoras por time. Meta diária corresponde à meta inteira por ciclo multiplicada pelos ciclos completos. A montagem permite ajustar a meta por ciclo antes de gerar novamente. Isso não altera as metas da TV.
- Verificação: 76 testes Python e navegador Edge local. O navegador conferiu geração, carga global, salvamento/reabertura, edição acima do limite, preservação após geração sem cobertura e impressão.

Limites desta entrega: a escolha de duplas é heurística, não um otimizador exato; não há confirmação de disponibilidade física de máquinas nem histórico de revisões. A validação com uma OP real ficará para o uso autorizado do proprietário no sistema; os testes não modificaram a produção.

## Plano recuperado

O commit `de1a0ae` documenta explicitamente:

1. Respeitar a sequência operacional exata.
2. Selecionar operadoras pelo menor tempo registrado para cada operação.
3. Limitar apoio a dois times para frente ou para trás do time principal.
4. Usar compatibilidade de equipamento quando não houver treinamento direto, sinalizando essa escolha.
5. Dividir operações entre times quando a carga ultrapassar o ciclo.
6. Identificar apoio e divisão visualmente.
7. Avisar quando não houver operadora treinada.

O commit `5e48e8c` acrescenta o controle da carga global da pessoa em todos os times durante o mesmo ciclo e o resumo por operadora na impressão. O commit `9293f03` acrescenta a persistência das operadoras e de suas atribuições.

Não foi localizado um documento separado com todo o plano anterior. As regras acima estão registradas nas mensagens dos commits e no código. O limite de duas pessoas por time existe como constante no algoritmo; não foi encontrado como requisito explícito no plano recuperado.

## Como funciona hoje

`/balanceamento` calcula a meta usando tempo padrão, minutos do turno, número informado de pessoas e ciclo. A tela `/balanceamento/montar` oferece montagem manual e o botão Auto.

O Auto envia apenas OP, ciclo e meta por ciclo para `/api/balanceamento/automatico`. O servidor percorre o roteiro, busca tempos individuais, usa compatibilidade de equipamento como alternativa e distribui operações em times. O resultado ocupa a tela e depende de uma ação separada para salvar.

A programação das metas da TV é independente do balanceamento, conforme a definição existente. A revisão não propõe misturar essas duas funções.

## Falhas reproduzidas

| Prioridade | Achado | Evidência e consequência |
| --- | --- | --- |
| 1 | A carga global da pessoa não é respeitada pelo automático | Com ciclo de 15 minutos, duas operações de 10 minutos foram atribuídas à mesma pessoa em dois times. Resultado: 20 minutos de trabalho no mesmo ciclo, com `ok: true`. |
| 1 | A divisão só trata o primeiro excedente | Uma operação com carga de 45 minutos foi dividida em 15 minutos no time 1 e 30 no time 2. A segunda parte continua acima do ciclo de 15. |
| 1 | O resultado automático não vira atribuições persistentes | O navegador cria `atribuicoes: []` para as operadoras e deixa o vínculo apenas dentro das operações. A gravação lê as atribuições vazias. Ao consultar o balanceamento salvo, as pessoas estão presentes, mas suas atribuições estão vazias. |
| 1 | A operação dividida perde a divisão ao reabrir | O salvamento atual usa apenas `sequencia_op.time_numero`. Para uma operação distribuída nos times 1 e 2, sobra somente o último time. No navegador, as partes de 1 e 2 peças reapareceram como 3 peças inteiras no time 2; o time 1 ficou sem operação. |
| 1 | A disponibilidade exibida não considera as operações do Auto | O resumo de carga soma apenas atribuições. Logo após o Auto, uma pessoa com partes de 15 e 30 minutos apareceu com carga global zero. Isso também afeta disponibilidade para apoio e impressão. |
| 2 | O limite de distância de apoio é contornável | Quando ninguém atende a distância, o algoritmo retorna a primeira candidata mesmo assim. A mesma pessoa foi colocada nos times 1, 2, 3 e 4, a três times de distância do principal. |
| 2 | Configuração de pessoas, times e grupo não chega ao algoritmo | A interface envia somente OP, ciclo e meta por ciclo. Na chamada isolada, pedir uma pessoa e um time resultou em três pessoas e dois times. Um grupo inexistente também foi ignorado. O grupo filtra somente a lista visual. |
| 2 | Pode selecionar pessoa inativa | Uma pessoa inativa com tempo menor foi escolhida antes de uma ativa. As consultas do automático não filtram situação. |
| 2 | Falta verificar os vínculos de empresa | O teste selecionou pessoa de outra fábrica e também permitiu gerar resultado para uma OP fora da fábrica do usuário. Embora a instalação atual seja de empresa única, as rotas precisam validar os vínculos dos registros. |
| 2 | As metas diária e por ciclo podem divergir | Para 540 minutos, duas pessoas e tempo de peça de 6,3 minutos, a meta diária calculada é 171. A meta arredondada por ciclo é 5; em 36 ciclos, isso exige 180 peças. Não há conciliação nem explicação da diferença. |

## Outros pontos identificados na leitura do código

Estes pontos foram identificados por inspeção; não tiveram reprodução própria nesta rodada:

- A seleção prefere uma pessoa que já está no time, mesmo quando há candidata mais rápida. Essa preferência precisa ser explicitada e só pode ocorrer se houver capacidade disponível.
- Ao fechar um time, a seleção não é refeita integralmente para o próximo. A referência do time principal também pode ser registrada antes de a operação ser efetivamente colocada.
- A restauração usa a meta completa e o tempo padrão da sequência para reconstruir a operação. O tempo individual aplicado pelo automático não é preservado como parte independente da alocação.
- Operações repetidas no roteiro são identificadas por `operacao_id`, em vez de pelo item específico da sequência. Atualizações atingem todas as ocorrências e a restauração procura a primeira ocorrência.
- O turno é enviado no payload, mas não é persistido na tabela de balanceamento. A reabertura recalcula metas com a configuração da página e não restaura integralmente minutos/meta do registro salvo.
- A confirmação manual permite informar quantidade acima da sugestão e não refaz a validação antes de aplicar. A rota de gravação também não valida sobrecarga, distância, cobertura do roteiro ou total de peças por operação.
- O indicador do time compara a carga total com um único ciclo. Para duas pessoas trabalhando em paralelo, é necessário mostrar carga por pessoa e capacidade total do time separadamente.
- Não há controle da disponibilidade física de máquinas na geração. Compatibilidade com uma máquina não confirma que ela esteja disponível.
- O histórico atual lista balanceamentos salvos, mas não conserva versões de cada alteração. Salvar substitui a composição anterior.
- Não foram encontrados testes dedicados ao automático na suíte existente. As reproduções desta auditoria cobrem casos que a validação anterior não exercitava.

## Regras esclarecidas pelo proprietário após a auditoria

Definição recebida em 07/10/2026:

- Cada time deve ter **duas operadoras principais**. A regra é uma dupla fixa por time, e não simplesmente um máximo de duas pessoas exibidas.
- Uma operadora pode usar o tempo livre para apoiar outros times, até **dois times à frente ou dois anteriores** do seu time principal. Apoio não muda o vínculo principal nem transforma a pessoa em outra operadora disponível.
- Para ciclo nominal de **15 minutos**, cada operadora pode ter carga global máxima de **16 minutos**. A soma inclui suas atividades no time principal e todos os apoios no mesmo ciclo.
- A tolerância de um minuto é global por pessoa e por ciclo, não um minuto adicional por operação ou por time visitado. A capacidade máxima de uma dupla é 32 minutos de carga no ciclo de 15, sem permitir que uma delas ultrapasse 16.
- A margem diária informada é de **18%** para troca de linha/agulha, água, banheiro e outras necessidades. Em jornada de 540 minutos, corresponde a **97,2 minutos por pessoa**, aproximadamente 97 minutos.
- Essa margem diária não aumenta o limite do ciclo para 18% acima de 15: o limite autorizado permanece em 16 minutos por pessoa.
- O proprietário confirmou que os tempos padrões cadastrados **já incluem os 18%**. O automático deve utilizá-los sem aplicar um novo acréscimo de 18% ou descontar novamente 97,2 minutos da jornada. Nenhuma alteração dos tempos ou metas foi realizada a partir dessa informação.

Exemplo de controle: time principal 3 pode apoiar os times 1, 2, 4 e 5; nunca 6. Se uma pessoa já tiver 13 minutos no principal e 2 em apoio, poderá receber no máximo mais 1 minuto somando os demais apoios.

Estas regras substituem a referência a um limite estrito de 15 minutos usada nos casos da auditoria. Os casos reproduzidos com 20, 30 e 45 minutos continuam inválidos mesmo com a tolerância agora autorizada.

## Implementação recomendada

### 1. Tornar o resultado consistente e preservável

Usar uma estrutura única de atribuição para montagem manual, geração automática, carga global, impressão e gravação. Cada atribuição deve identificar o item do roteiro, operadora, time, quantidade e tempo aplicado. Persistir cada parte separada; reabrir deve reconstruir exatamente a mesma composição. Conservar também turno, parâmetros utilizados e versão do balanceamento.

### 2. Corrigir as restrições da geração

Considerar somente pessoas ativas, autorizadas e disponíveis dentro do grupo definido. Controlar carga global por pessoa, dividir até que todas as partes caibam, respeitar a distância de apoio e identificar operações sem cobertura. Não contornar uma restrição para conseguir retornar sucesso. Verificar também disponibilidade de equipamento.

O limite de pessoas principais por time foi esclarecido: exatamente duas, com apoios tratados separadamente. A configuração de pessoas e times deve refletir essa composição; pessoas de apoio não podem ser contadas novamente como integrantes de outra dupla. Ainda é necessário distinguir quantidade de times desejada de eventual sugestão de times necessários, sem substituir silenciosamente os valores informados.

### 3. Validar a proposta antes de salvar

Mostrar cobertura do roteiro, pessoas utilizadas, carga e tempo livre por pessoa, ocupação dos times, apoio e operações pendentes. Se a capacidade não atender a meta, explicar o impedimento e a capacidade atingível. A validação deve ser repetida no servidor ao salvar; a tela não pode ser a única proteção.

### 4. Validar com uma OP real

Depois das correções, usar uma OP com roteiro e banco de tempos conferidos. Comparar geração, ajuste manual, impressão, salvamento e reabertura. Validar os dados reais sem substituir automaticamente o balanceamento em uso.

## Evidências e localização

- Regras históricas: commits `de1a0ae`, `5e48e8c`, `9293f03`.
- Algoritmo: `app.py:1385`.
- Seleção e apoio: `app.py:1493`.
- Divisão: `app.py:1544`.
- Gravação: `app.py:1182`.
- Carregamento: `app.py:1240`.
- Conversão do Auto: `templates/balanceamento_montar.html:766`.
- Carga global: `templates/balanceamento_montar.html:482`.
- Restauração: `templates/balanceamento_montar.html:364`.
- Payload de gravação: `templates/balanceamento_montar.html:1211`.
- Estrutura das tabelas: `models.py:410`.
- Reprodutor isolado: `test-results/auditoria_balanceamento.py`.
- Resultado dos casos: `test-results/auditoria_balanceamento.json`.
- Reprodutor no navegador: `test-results/auditoria_balanceamento_browser.cjs`.
- Imagens antes/depois: `test-results/balanceamento-auditoria-antes.png` e `test-results/balanceamento-auditoria-depois.png`.

Os arquivos em `test-results` são artefatos locais ignorados pelo Git. O reprodutor não deve ser usado para substituir dados de produção; ele utiliza a conexão temporária da suíte de testes.
