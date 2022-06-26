# 1º Relatóio: Etapa AI-a (Analisador Léxico e Sintático)

1. Qual é o nome do relator?

    > Bruno Barros

2. A etapa foi completamente ou parcialmente concluída?

    > Acreditamos que totalmente, dado que o lexer e parser foram implementados e parecem funcionar corretamente.

3. No caso de parcialmente concluída, o que não foi concluído?

    > 

4. O programa passa nos testes automatizados?
    
    > Passa em todos exceto 2. No entanto, acreditamos que no caso dos 2 em que não passa, o problema é nos testes.

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    > O lexer não passa em um teste da quantidade de "minus" e em um da quantidade de "tokens". Alterando os testes para imprimir o nome do arquivo em que dá erro, vimos que isso ocorre para o arquivo "Factorial.java". Olhando esse arquivo, concluímos que o problema parece ser no teste e não no lexer (de fato, o teste parece ignorar a existência de um token "minus", gerando a diferença de um "minus" e um token). 

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Inicialmente não estávamos conseguindo executar os testes, e só conseguimos depois que editamos a função de erro no lexer para não parar quando se encontra um erro. Também foi difícil resolver os conflitos shift-reduce.

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > A divisão do trabalho inicialmente foi assim: George escrever o lexer, o Felipe escrever as regras do parser envolvendo Expression, Type e Identifier, e eu (Bruno) escrever o restante das regras do parser.
    > No fim das contas, um acabou fazendo um pouco da parte do outro também - por exemplo, para testar o lexer o George resolveu escrever uma versão provisória do parser, e eu fui encontrando erros no lexer e corrigindo.


# 2º Relatóio: Etapa AI-b (Árvores Sintática Abstrata e Análise Semântica)

1. Qual é o nome do relator?

    > George Harrison

2. A etapa foi completamente ou parcialmente concluída?

    > Parcialmente concluída.

3. No caso de parcialmente concluída, o que não foi concluído?

    > Parte dos testes falhou, então as implementações não estão totalmente corretas.

4. O programa passa nos testes automatizados?
    
    > Não, pois falhou em 25 deles.

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    > Inicialmente alguns arquivos não conseguiam ser parseados para um Program (ou seja, sua árvore sintática abstrata). Resolvemos consertar os erros sintáticos dos arquivos, mas de modo a manter o mesmo número de erros semânticos.

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Implementar os visitors e encontrar os erros nos testes relacionados às implementações.

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > Bruno implementou a construção da árvore abstrata sintática (ast);
    > Felipe implementou o preenchimento da tabela de símbolos (FillSymbolTableVisitor);
    > George implementou a checagem de tipos (TypeCheckingVisitor)

# 3º Relatóio: Etapa AI-c (Tradução para o Código Intermediário)

1. Qual é o nome do relator?

    > Felipe Bezerra

2. A etapa foi completamente ou parcialmente concluída?

    > A etapa foi totalmente concluída, mas possivelmente com alguns erros.

3. No caso de parcialmente concluída, o que não foi concluído?

    > Escreva sua resposta aqui

4. O programa passa nos testes automatizados?
    
    > Sim, ele passa. Não há testes automatizados específicos para essa etapa, mas o programa passa nos testes das etapas anteriores

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    >  Não, nenhum erro de execução foi encontrado. O codigo executa de maneira aparentemente correta para todas as entradas (não há erro de execucao e os visitors geram um output no formato esperado).

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Implementar alguns dos métodos foi difícil, como os que envolvem Identifier, pois algumas partes da teoria foram mais difíceis de entender.

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > Escreva sua resposta aqui


# 4º Relatóio: Etapa AI-d (Seleção de Instruções)

1. Qual é o nome do relator?

    > Escreva sua resposta aqui

2. A etapa foi completamente ou parcialmente concluída?

    > Escreva sua resposta aqui

3. No caso de parcialmente concluída, o que não foi concluído?

    > Escreva sua resposta aqui

4. O programa passa nos testes automatizados?
    
    > Escreva sua resposta aqui

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    > Escreva sua resposta aqui

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Escreva sua resposta aqui

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > Escreva sua resposta aqui


# 5º Relatóio: Etapa AI-e (Alocação de Registradores)

1. Qual é o nome do relator?

    > Escreva sua resposta aqui

2. A etapa foi completamente ou parcialmente concluída?

    > Escreva sua resposta aqui

3. No caso de parcialmente concluída, o que não foi concluído?

    > Escreva sua resposta aqui

4. O programa passa nos testes automatizados?
    
    > Escreva sua resposta aqui

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    > Escreva sua resposta aqui

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Escreva sua resposta aqui

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > Escreva sua resposta aqui


# 6º Relatóio: Etapa AI-f (Integração e Geração do Código Final)

1. Qual é o nome do relator?

    > Escreva sua resposta aqui

2. A etapa foi completamente ou parcialmente concluída?

    > Escreva sua resposta aqui

3. No caso de parcialmente concluída, o que não foi concluído?

    > Escreva sua resposta aqui

4. O programa passa nos testes automatizados?
    
    > Escreva sua resposta aqui

5. Algum erro de execução foi encontrado para alguma das entradas? Quais?
    
    > Escreva sua resposta aqui

6. Quais as dificuldades encontradas para realização da etapa do projeto?
    
    > Escreva sua resposta aqui

7. Qual a participação de cada membro da equipe na etapa de execução?
    
    > Escreva sua resposta aqui
