from __future__ import annotations
from abc import abstractmethod
from collections import deque
import sys
from typing import Set
from pymjc.back import assem, flowgraph, graph
from pymjc.front import frame, temp, tree, canon


class RegAlloc (temp.TempMap):
    def __init__(self, frame: frame.Frame, instr_list: assem.InstrList):
        self.frame: frame.Frame = frame
        self.instrs: assem.InstrList = instr_list
        
        # estes registradores não são limpos pela reiniciação do Color
        # worklist para nós do tipo Move
        self.worklistMoveNodes: set[graph.Node] = set()
        # registradores temporadores gerados pelo método spills do color
        self.spillTemps: set[temp.Temp] = set()
        
        # procedimento principal
        proceed = True
        while (proceed):
            # análise de liveness
            self.assemFlowGraph = flowgraph.AssemFlowGraph(self.instrs)
            self.liveness = Liveness(self.assemFlowGraph)
            
            # clear se torna responsabilidade de Color (isso é bom para separação de conceitos, 
            # mas torna o clean-up das estruturas um pouco mais lento)
            registerList = temp.TempList()
            for register in self.frame.registers():
                registerList.add_tail(register)
            self.color = Color(self.liveness, self.frame, registerList)
            self.color.setWorklistMoveNodes(self.worklistMoveNodes)
            self.color.setSpillTemps(self.spillTemps)
            self.color.setFP(frame.FP())
            self.color.setFlowGraph(self.assemFlowGraph)

            # init
            self.color.init()
            
            # build
            nodeList = self.assemFlowGraph.nodes()
            while (nodeList != None):
                node = nodeList.head
                # live := liveOut(b)
                live: set[temp.Temp] = self.liveness.out(node).copy()
                isMoveInstr = self.assemFlowGraph.is_move(node)
                if (isMoveInstr):
                    uses: temp.TempList = self.assemFlowGraph.use(node)
                    while (uses != None):
                        live.remove(uses.head)
                        uses = uses.tail
                    # moveList[n] ∪ {I}
                    uses = self.assemFlowGraph.use(node)
                    while (uses != None):
                        moveNodeSet = self.color.getMoveNodeSet(self.liveness.tnode(uses.head))
                        moveNodeSet.add(node)
                        uses = uses.tail
                    defs = self.assemFlowGraph.deff(node)
                    while (defs != None):
                        moveNodeSet = self.color.getMoveNodeSet(self.liveness.tnode(defs.head))
                        moveNodeSet.add(node)
                        defs = defs.tail
                    # worklistMoves ← worklistMoves ∪ {I}
                    self.worklistMoveNodes.add(node)
                # live ← live ∪ def(I)
                defs = self.assemFlowGraph.deff(node)
                while (defs != None):
                    live.add(defs.head)
                    defs = defs.tail
                # forall d ∈ def(I)
                defs = self.assemFlowGraph.deff(node)
                while (defs != None):
                    # forall l ∈ live
                    for liveTemp in live:
                        # AddEdge entre Temps
                        if (liveTemp!=defs.head):
                            self.color.addEdge(self.liveness.tnode(liveTemp), self.liveness.tnode(defs.head))
                    defs = defs.tail
                nodeList = nodeList.tail
            
            # makeWorklist
            self.color.makeWorklist()
            
            # coloração dos nós para calcular os nós de transbordamento
            spills_list: temp.TempList = self.color.spills()
            if (spills_list.head!=None):
                # há nós transbordando, então reescreve-se o programa
                self.rewriteProgram()
            else:
                # não há nós transbordando, então os registradores são suficientes para a alocação
                proceed = False
        
        # passo final (alocação de registradores)
        auxiliarInstrList = self.instrs
        instrListTail = None
        # iteração da lista de instruções
        insns = None
        while (auxiliarInstrList!=None):
            currentInstr = auxiliarInstrList.head
            # se a instrução é do tipo move, pule se def e use têm o mesmo alias
            # (semelhante a x <- x)
            if isinstance((currentInstr,assem.MOVE)):
                defTemp = currentInstr.deff().head
                useTemp = currentInstr.use().head
                defAlias = self.color.getAlias(self.liveness.tnode(defTemp))
                useAlias = self.color.getAlias(self.liveness.tnode(useTemp))
                if (defAlias==useAlias):
                    continue
            # se a lista de instruções está vazia, cria uma nova, senão, atualiza
            if (insns is None):
                insns = instrListTail = assem.InstrList(auxiliarInstrList.head, None)
            else:
                instrListTail = instrListTail.tail = assem.InstrList(auxiliarInstrList.head, None)
            auxiliarInstrList = auxiliarInstrList.tail
        self.instrs = insns



    # classe auxiliar para memorizar a head e tail mais distante de um registrador temporário
    class MemHeadTailTemp:
        def __init__(self, instrList: assem.InstrList, temp: temp.Temp):
            self.head = instrList
            self.temp = temp
            self.tail = self.head
            while (self.tail != None):
                if (self.tail.tail == None):
                    break
                self.tail = self.tail.tail

    # gera uma instrução do tipo Fetch
    def genFetch(self, access: frame.Access, temp: temp.Temp) -> RegAlloc.MemHeadTailTemp:
        # registrador temporário vai para a lista de transbordamento
        self.spillTemps.add(temp)
        # instancia o Fetch
        fetchInstr = tree.MOVE(tree.TEMP(temp), access.exp(tree.TEMP(self.frame.FP())))
        # retorna o HeadTail correspondente
        return RegAlloc.MemHeadTailTemp(self.frame.codegen(canon.Canon.linearize(fetchInstr)), temp)
    # gera uma instrução do tipo Store
    def getStore(self, access: frame.Access, temp: temp.Temp) -> RegAlloc.MemHeadTailTemp:
        # semelhante ao Fetch
        self.spillTemps.add(temp)
        s: tree.Stm = tree.MOVE(access.exp(tree.TEMP(self.frame.FP())), tree.TEMP(temp))
        return RegAlloc.MemHeadTailTemp(self.frame.codegen(canon.Canon.linearize(s)), temp)

    # auxiliar para reescrever o programa
    def rewriteProgram(self):
        accessTable: dict[temp.Temp, frame.Access] = {}
        for node in self.color.spillNodes:
            # adiciona um acesso à memória à tabela (note que o alloc escapa)
            accessTable[self.liveness.gtemp(node)] = frame.alloc_local(True)
        # etapa de reescrita do programa
        insnsPast = self.instrs
        tail = self.instrs = None
        while (insnsPast != None):
            # atualização de instruções com Fetch
            tempList = insnsPast.head.use()
            while (tempList != None):
                temp = tempList.head
                access = accessTable.get(temp)
                # se não há acesso, transborda
                if (access != None):
                    result = self.genFetch(access, temp)
                    # atualização da cauda ou das instruções, de acordo com estas
                    if (self.instrs != None):
                        tail.tail = result.head
                    else:
                        self.instrs = result.head
                    tail = result.tail
                # introdução da nova instrução
                newInstrList = assem.InstrList(insnsPast.head, None)
                # atualização da cauda ou das instruções, de acordo com estas
                if (self.instrs != None):
                    tail = tail.tail = newInstrList
                else:
                    self.instrs = tail = newInstrList
                # atualização da instrução no caso de Store
                defTempList = insnsPast.head.deff()
                while (defTempList != None):
                    temp = defTempList.head
                    access = accessTable.get(temp)
                    # se não há acesso, transborda
                    if (access != None):
                        result = self.getStore(access, defTempList.head)
                        # atualização da cauda ou das instruções, de acordo com estas
                        if (self.instrs != None):
                            tail.tail = result.head
                        else:
                            self.instrs = result.head
                        tail = result.tail
                        defTempList.head = result.temp
                    defTempList = defTempList.tail
            insnsPast = insnsPast.tail


    def temp_map(self, temp: temp.Temp) -> str:
        temp_str: str = self.frame.temp_map(temp)
        if (temp_str==None):
            temp_str = self.color.temp_map(temp)
        return temp_str
    

class Color(temp.TempMap):
    def __init__(self, ig: InterferenceGraph, initial: temp.TempMap, registers: temp.TempList):
        self.interferenceGraph = ig
        self.frame = initial
        self.registers = registers
        # (re)inicialização
        # nós que são coloridos antes ou durante do algoritmo
        self.preColored: set[graph.Node] = set()
        self.normalColored: set[graph.Node] = set()
        # nós categorizados em iniciais, de transbordamento e de aglutinação
        self.initialNodes: set[graph.Node] = set()
        self.spillNodes: set[graph.Node] = set()
        self.coalesceNodes: set[graph.Node] = set()
        # pilha de coloração (usando a estrutura deque de Collections como uma pilha)
        self.nodeStack: deque[graph.Node] = deque()
        # listas para as etapas de simplificação, congelamento e transbordamento
        self.simplifyWorklist: set[graph.Node] = set()
        self.freezeWorklist: set[graph.Node] = set()
        self.spillWorklist: set[graph.Node] = set()
        # nós Move (representam instrução do tipo a <- b)
        self.coalesceMoveNodes: set[graph.Node] = set()
        self.constrainMoveNodes: set[graph.Node] = set()
        self.freezeMoveNodes: set[graph.Node] = set()
        self.activeModeNodes: set[graph.Node] = set()
        # custos de transbordamento
        self.spillCost: dict[graph.Node, int] = {}
        # tabela de moves (similar à lista de adjacências abaixo, mas para nós Move)
        self.moveNodesList: dict[graph.Node, set[graph.Node]] = {}
        # adjacências
        self.adjacenceSets: set[Edge] = set()
        self.adjacenceList: dict[graph.Node, set[graph.Node]] = {}
        # tabelas de alias, cor e grau dos nós
        self.nodeAliasTable: dict[graph.Node, graph.Node] = {}
        self.nodeColorTable: dict[graph.Node, graph.Node] = {}
        self.nodeDegreeTable: dict[graph.Node, int] = {}
    
    def setWorklistMoveNodes(self, moveNodes: set[graph.Node]):
        self.worklistMoveNodes: set[graph.Node] = set()
        for node in moveNodes:
            self.worklistMoveNodes.add(node)
    def setSpillTemps(self, spillTemps: set[temp.Temp]):
        self.spillTemps = spillTemps
    def setFP(self, fp: frame.Frame):
        self.FP: frame.Frame = fp
    def setFlowGraph(self, flowGraph: flowgraph.AssemFlowGraph):
        self.assemFlowGraph = flowGraph
    
    def init(self):
        # const para Integer.MAX_VALUE
        INTEGERMAXVALUE: int = sys.maxsize
        # criação da lista de temporários pré-coloridos
        tempReg = self.registers.head
        while (tempReg!=None):
            node = self.interferenceGraph.tnode(tempReg)
            # adiciona nó com custo de spill máximo
            self.preColored.add(node)
            self.spillCost[node] = INTEGERMAXVALUE
            # atualização da tabela de cores e de grau
            self.nodeColorTable[node] = node
            self.nodeDegreeTable[node] = 0
        # criação da lista de registradores para os não-pré-coloridos
        nodeList = self.interferenceGraph.nodes()
        while (nodeList != None):
            node = nodeList.head
            # se o nó não está nos pré-coloridos
            if (node not in self.preColored):
                # adiciona aos iniciais
                self.initialNodes.add(node)
                # definição do custo de spill, depois atualizando a tabela de graus
                if (self.interferenceGraph.gtemp(node) in self.spillTemps):
                    self.spillCost[node] = INTEGERMAXVALUE
                elif (node not in self.preColored):
                    self.spillCost[node] = 1
                self.nodeDegreeTable[node] = 0
            nodeList = nodeList.tail
    
    def getAlias(self, node: graph.Node) -> graph.Node:
        # se está na lista de aglutinação, basta retorná-lo
        if (node not in self.coalesceNodes):
            return node
        # senão, obtem-se o nó referente pela tabela de alias
        return self.nodeAliasTable.get(node)
    def getMoveNodeSet(self, node: graph.Node) -> set[graph.Node]:
        if (node==None):
            raise Exception("Node is null")
        moveSet = self.moveNodesList.get(node)
        if (moveSet==None):
            moveSet = set()
            self.moveNodesList[node] = moveSet
        return moveSet

    def getAdjacenceList(self, node: graph.Node) -> set[graph.Node]:
        adjList = self.adjacenceList.get(node)
        if (adjList==None):
            adjList = set()
            self.adjacenceList[node] = adjList
        return adjList
    def adjacent(self, node: graph.Node) -> set[graph.Node]:
        unionTable = set(self.nodeStack).union(self.coalesceNodes)
        adjacence = self.getAdjacenceList(node)
        adjacent = set()
        for node in adjacence:
            # adjList[n] \ (selectStack ∪ coalescedNodes)
            if node not in unionTable:
                adjacent.add(node)
        return adjacent
    def decrementDegree(self, node: graph.Node):
        if (node in self.preColored):
            return
        d = self.nodeDegreeTable.get(node)
        self.nodeDegreeTable[node] = d-1

        k = len(self.preColored)
        if (d==k):
            # {node} ∪ Adjacent(node)
            adjacents = self.adjacent(node)
            adjacents.add(node)
            # EnableMoves({node} ∪ Adjacent(node))
            for auxNode in adjacents:
                self.enableMoves(auxNode)
            self.spillWorklist.remove(node)
            # se é MOVE-related, congela; senão, simplifica
            if (self.moveRelated(node)):
                self.freezeWorklist.add(node)
            else:
                self.simplifyWorklist.add(node)
    def enableMoves(self, node: graph.Node):
        # forall n ∈ nodes
        # forall m ∈ NodeMoves(n)
        nodeMoves = self.nodeMoves(node)
        for node in nodeMoves:
            # if m ∈ activeMoves then
            if (node in self.activeMoveNodes):
                # activeMoves ← activeMoves \ {m}
                self.activeMoveNodes.remove(node)
                # worklistMoves ← worklistMoves ∪ {m}
                self.worklistMoveNodes.add(node)
    def addEdge(self, u: graph.Node, v: graph.Node):
        e = Edge.get_edge(u, v)
        e_rev = Edge.get_edge(v, u)
        # if ((u,v) ∉ adjSet) ∧ (u ≠ v) then
        if ((e not in self.adjacenceSets) and (e != e_rev)):
            self.adjacenceSets.add(e)
            self.adjacenceSets.add(e_rev)
            # if u ∉ precolored then
            if (u not in self.preColoredNodes):
                # adjList[u] ← adjList[u] ∪ {v}
                # degree[u] ← degree[u]+1
                self.adjacenceList(u).add(v)
                self.nodeDegreeTable.put(u, self.nodeDegreeTable(u) + 1)
            # if v ∉ precolored then
            if (v not in self.preColoredNodes):
                # adjList[v] ← adjList[v] ∪ {u}
                # degree[v] ← degree[v]+1
                self.adjacenceList(v).add(u)
                self.nodeDegreeTable.put(v, self.nodeDegreeTable(v) + 1)
    
    # retorna os nós relacionados a MOVE deste nó node
    def nodeMoves(self, node: graph.Node) -> set[graph.Node]:
        nodeSet: set[graph.Node] = set()
        moveSetOfNode = self.getMoveNodeSet(node)
        activeOrNode = self.activeModeNodes.union(self.worklistMoveNodes)
        for node in moveSetOfNode:
            if node in activeOrNode:
                nodeSet.add(node)
        return nodeSet
    # retorna se o nó está relacionado a MOVES
    def moveRelated(self, node: graph.Node) -> bool:
        return len(self.nodeMoves(node)) != 0
    def makeWorklist(self):
        k = len(self.preColored)
        initial = list(self.initialNodes)
        for node in initial:
            # if degree[n] ≥ K then
            if (self.nodeDegreeTable.get(node) >= k):
                # spillWorklist ← spillWorklist ∪ {n}
                self.spillWorklist.add(node)
            # else if MoveRelated(n) then
            elif (self.moveRelated(node)):
                # freezeWorklist ← freezeWorklist ∪ {n}
                self.freezeWorklist.add(node)
            else:
                # simplifyWorklist ← simplifyWorklist ∪ {n}
                self.simplifyWorklist.add(node)
    def addWorklist(self, node: graph.Node):
        check1 = node not in self.preColored
        check2 = not self.moveRelated(node)
        check3 = self.nodeDegreeTable.get(node)<len(self.preColored)
        if (check1 and check2 and check3):
            self.freezeWorklist.remove(node)
            self.simplifyWorklist.add(node)

    def ok(self, t: graph.Node, r: graph.Node) -> bool:
        K: int = len(self.preColoredNodes)
    	result: bool = (t in self.preColoredNodes) or (self.nodeDegreeTable(t) < K) or (Edge.getEdge(t, r) in self.adjacenceSets)
    	return result
    def CoalesceAuxiliarFirstChecking(self, u: graph.Node, v: graph.Node):
    	if not (u in self.preColoredNodes):
    		return False
    	for t in self.Adjacent(v):
    		if not self.OK(t,u):
    			return False
    	return True
    def CoalesceAuxiliarSecondChecking(self, u: graph.Node, v: graph.Node):
    	if (u in self.preColoredNodes):
    		return False

    	adjacent = {self.Adjacent(u)}
    	adjacent.addAll(self.Adjacent(v))

    	return self.Conservative(adjacent)
    def combine(self, u: graph.Node, v: graph.Node) -> bool:
        if (v in self.freezeWorklist):
            self.freezeWorklist.remove(v)
        else:
            self.spillWorklist.remove(v)
        self.coalesceNodes.add(v)
        self.nodeAliasTable[v] = u
        vMoveNodes = self.getMoveNodeSet(v)
        for vMoveNode in vMoveNodes:
            self.getMoveNodeSet(u).add(vMoveNode)
        self.enableMoves(v)
        adjacence = self.adjacent(v)
        for t in adjacence:
            self.addEdge(t, u)
            self.decrementDegree(t)
        degreeCheck = self.nodeDegreeTable.get(u) >= len(self.preColored)
        inCheck = u in self.freezeWorklist
        if (degreeCheck and inCheck):
            self.freezeWorklist.remove(u)
            self.spillWorklist.add(u)
    def freezesMoves(self, u: graph.Node):
        K = len(self.preColoredNodes)

    	for m in self.NodeMoves(u):
    		x: graph.Node = self.livenessOutput.tnode(self.assemFlowGraph.deff(m).head)
    		y: graph.Node = self.livenessOutput.tnode(self.assemFlowGraph.use(m).head)
    		v: graph.Node
    		if (self.GetAlias(u) == self.GetAlias(y)):
    			v = self.GetAlias(x)
    		else:
    			v = self.GetAlias(y)
    		self.activeMoveNodes.discard(m)
    		self.freezeMoveNodes.add(m)
    		if (self.NodeMoves(v).size() == 0 and self.nodeDegreeTable(v) < K):
    			self.freezeWorklist.discard(v)
    			self.simplifyWorklist.add(v)


    def Simplify(self):
        for n in self.simplifyWorklist.copy():
    		self.simplifyWorklist.discard(n)
    		self.nodeStack.append(n)
    		for m in self.Adjacent(n):
    			self.DecrementDegree(m)
    def Coalesce(self):
        m: graph.Node = None
    	for n in self.worklistMoveNodes.copy():
    		m = n
    	self.worklistMoveNodes.discard(m)

    	x: graph.Node = self.GetAlias(self.livenessOutput.tnode(self.assemFlowGraph.instr(m).deff().head));
    	y: graph.Node = self.GetAlias(self.livenessOutput.tnode(self.assemFlowGraph.instr(m).use().head));

    	u: graph.Node = None
    	v: graph.Node = None

    	if (y in self.preColoredNodes):
    		u = y
    		v = x
    	else:
    		u = x
    		v = y

    	e: Edge = Edge.getEdge(u,v)
    	self.worklistMoveNodes.discard(m)

    	if (u==v):
    		self.coalesceMoveNodes.add(m)
    		self.AddWorkList(u)
    	elif ( (v in self.preColoredNodes) or (e in self.adjacenceSets) ):
    		self.constrainMoveNodes.add(m)
    		self.AddWorklist(u)
    		self.AddWorklist(v)
    	elif (self.CoalesceAuxiliarFirstChecking(u, v) or self.CoalesceAuxiliarSecondChecking(u, v)):
    		self.coalesceMoveNodes.add(m)
    		self.Combine(u, v)
    		self.AddWorklist(u)
    	else:
    		self.activeMoveNodes.add(m)

    def Freeze(self):
        u: graph.Node = self.freezeWorklist[0]
    	self.freezeWorklist.discard(u)
    	self.simplifyWorklist.add(u)
    	
    	FreezeMoves(u)
    def SelectSpill(self):
        node = self.spillWorklist.pop()
        cost = self.spillCost.get(node)
        for spill in self.spillWorklist:
            if (self.spillCost.get(spill) < cost):
                node = spill
        self.simplifyWorklist.add(node)
        self.freezesMoves(node)

    def spills(self) -> temp.TempList:
        # loop de coloração
        doLoop = True
        while (doLoop):
            if (len(self.simplifyWorklist)!=0):
                self.Simplify()
            elif (len(self.worklistMoveNodes)!=0):
                self.Coalesce()
            elif (len(self.freezeWorklist)!=0):
                self.Freeze()
            elif (len(self.spillWorklist)!=0):
                self.SelectSpill()
            
            # colorir os nós (AssignColors)
            # enquanto a pilha de nós não está vazia...
            while (len(self.nodeStack)!=0):
                node = self.nodeStack.pop()
                okColors =self.preColored.copy()
                if (self.getAlias(node) in self.preColored):
                    continue
                okColors.remove(self.interferenceGraph.tnode(self.FP))

                adjList = self.getAdjacenceList(node)
                # forall w ∈ adjList[n]
                for node in adjList:
                    used = self.preColored.union(self.normalColored)
                    alias = self.getAlias(node)
                    # if GetAlias(w) ∈ (coloredNodes ∪ precolored) then
                    if (alias in used):
                        okColors.remove(self.nodeColorTable.get(alias))
                    # se okColors está vazia, transborda, senão colore normalmente
                if (len(okColors)==0):
                    self.spillNodes.add(node)
                else:
                    self.normalColored.add(node)
                    # let c ∈ okColors
                    c = okColors.pop()
                    okColors.add(c)
                    self.nodeColorTable[node] = c
            # forall n ∈ coalescedNodes
            for node in self.coalesceNodes:
                # color[n] ← color[GetAlias(n)]
                aliases = self.getAlias(node)
                aliasNode = self.nodeColorTable.get(aliases)
                if (aliasNode != None):
                    self.nodeColorTable[node] = aliasNode


            simplifyEmpty = len(self.simplifyWorklist)==0 
            moveNodesEmpty = len(self.worklistMoveNodes)==0
            freezeEmpty = len(self.freezeWorklist)==0
            spillEmpty = len(self.spillWorklist)==0
            doLoop = not (simplifyEmpty and moveNodesEmpty and freezeEmpty and spillEmpty)

        # retorna lista de registradores transbordados
        tempList = temp.TempList()
        for node in self.spillNodes:
            tempList.add_tail(self.interferenceGraph.gtemp(node))
        return tempList

    def temp_map(self, temp: temp.Temp) -> str:
        node = self.nodeColorTable.get(self.interferenceGraph.tnode(temp))
        return self.frame.temp_map(self.interferenceGraph.gtemp(node))

class InterferenceGraph(graph.Graph):
    
    @abstractmethod
    def tnode(self, temp:temp.Temp) -> graph.Node:
        pass

    @abstractmethod
    def gtemp(self, node: graph.Node) -> temp.Temp:
        pass

    @abstractmethod
    def moves(self) -> MoveList:
        pass
    
    def spill_cost(self, node: graph.Node) -> int:
      return 1


class Liveness (InterferenceGraph):

    def __init__(self, flow: flowgraph.FlowGraph):
        super(Liveness, self).__init__()
        self.live_map = {}
        
        #Flow Graph
        self.flowgraph: flowgraph.FlowGraph = flow
        
        #IN, OUT, GEN, and KILL map tables
        #The table maps complies with: <Node, Set[Temp]>
        self.in_node_table = {}
        self.out_node_table = {}
        self.gen_node_table = {}
        self.kill_node_table = {}

        #Util map tables
        #<Node, Temp>
        self.rev_node_table = {}
        #<Temp, Node>
        self.map_node_table = {}
        
        #Move list
        self.move_list: MoveList = None

        self.build_gen_and_kill()
        self.build_in_and_out()
        self.build_interference_graph()
    
    def add_edge(self, source_node: graph.Node, destiny_node: graph.Node):
        if (source_node is not destiny_node and not destiny_node.comes_from(source_node) and not source_node.comes_from(destiny_node)):
            super().add_edge(source_node, destiny_node)

    def show(self, out_path: str) -> None:
        if out_path is not None:
            sys.stdout = open(out_path, 'w')   
        node_list: graph.NodeList = self.nodes()
        while(node_list is not None):
            temp: temp.Temp = self.rev_node_table.get(node_list.head)
            print(temp + ": [ ")
            adjs: graph.NodeList = node_list.head.adj()
            while(adjs is not None):
                print(self.rev_node_table.get(adjs.head) + " ")
                adjs = adjs.tail

            print("]")
            node_list = node_list.tail
    
    def get_node(self, temp: temp.Temp) -> graph.Node:
      requested_node: graph.Node = self.map_node_table.get(temp)
      if (requested_node is None):
          requested_node = self.new_node()
          self.map_node_table[temp] = requested_node
          self.rev_node_table[requested_node] = temp

      return requested_node

    def node_handler(self, node: graph.Node):
        def_temp_list: temp.TempList = self.flowgraph.deff(node)
        while(def_temp_list is not None):
            got_node: graph.Node  = self.get_node(def_temp_list.head)

            for live_out in self.out_node_table.get(node):
                current_live_out = self.get_node(live_out)
                self.add_edge(got_node, current_live_out)

            def_temp_list = def_temp_list.tail

  
    def move_handler(self, node: graph.Node):
        source_node: graph.Node  = self.get_node(self.flowgraph.use(node).head)
        destiny_node: graph.Node = self.get_node(self.flowgraph.deff(node).head)

        self.move_list = MoveList(source_node, destiny_node, self.move_list)
    
        for temp in self.out_node_table.get(node):
            got_node: graph.Node = self.get_node(temp)
            if (got_node is not source_node ):
                self.addEdge(destiny_node, got_node)


    def out(self, node: graph.Node) -> Set[temp.Temp]:
        temp_set = self.out_node_table.get(node)
        return temp_set


    def tnode(self, temp:temp.Temp) -> graph.Node:
        node: graph.Node = self.map_node_table.get(temp)
        if (node is None ):
            node = self.new_node()
            self.map_node_table[temp] = node
            self.rev_node_table[node] = temp
        
        return node

    def gtemp(self, node: graph.Node) -> temp.Temp:
        temp: temp.Temp = self.rev_node_table.get(node)
        return temp

    def moves(self) -> MoveList:
        return self.move_list

    #Estou usando as tabelas IN e OUT como o in' e o out' do algoritmo, e as tabelas KILL e GEN como o "in" e o "out"
    #Isto é, KILL e GEN armazenam o novo valor de "in" e "out" calculado em cada iteração, e IN e OUT armazenam o anterior
    #Também estou usando esse método para criar os nós e adicioná-los aos dois mapas
    def build_gen_and_kill(self):
        #Percorremos os nós do flowgraph
        nodes: graph.NodeList = self.flowgraph.mynodes

        while (nodes is not None):

            #Para cada temp usado no use ou no deff de algum nó do flowgraph, criamos um nó nesse grafo e preenchemos os mapas
            temps: temp.TempList = self.flowgraph.use(nodes.head)
            while (temps is not None):
                temp: temp.Temp = temps.head
                if (self.map_node_table.get(temp) is None):
                    new_node: graph.Node = self.new_node()
                    self.rev_node_table[new_node] = temp
                    self.map_node_table[temp] = new_node
                temps = temps.tail
            temps: temp.TempList = self.flowgraph.deff(nodes.head)
            while (temps is not None):
                temp: temp.Temp = temps.head
                if (self.map_node_table.get(temp) is None):
                    new_node: graph.Node = self.new_node()
                    self.rev_node_table[new_node] = temp
                    self.map_node_table[temp] = new_node
                temps = temps.tail

            #Inicializamos 'gen' e 'kill'
            self.gen_node_table[nodes.head] = set()
            self.kill_node_table[nodes.head] = set()

            nodes = nodes.tail

    def build_in_and_out(self):

        nodes = self.flowgraph.mynodes
        equal = False

        #repeat
        while not equal:

            #for each n
            while (nodes is not None):

                node: graph.Node = nodes.head

                #in′[n] ← in[n]
                self.in_node_table[node] = self.kill_node_table.get(node)

                #out′[n] ← out[n]
                self.out_node_table[node] = self.gen_node_table.get(node)

                #in[n] ← use[n] U (out[n] − def[n])
                new_kill = self.gen_node_table.get(node)
                deff: temp.TempList = self.flowgraph.deff(node)
                while (deff is not None):
                    d: temp.Temp = deff.head
                    new_kill.discard(d)
                    deff = deff.tail
                use: temp.TempList = self.flowgraph.use(node)
                while (use is not None):
                    d: temp.Temp = use.head
                    new_kill.add(d)
                    use = use.tail
                self.kill_node_table[node] = new_kill

                #out[n] ← U s in succ[n] (in[s])
                new_gen = set()
                succ: graph.NodeList = node.succ()
                while (succ is not None):
                    s: graph.Node = succ.head
                    new_gen.union(self.kill_node_table.get(s))
                    succ = succ.tail
                self.gen_node_table[node] = new_gen

                nodes = nodes.tail

            #until in′[n] = in[n] and out′[n] = out[n] for all n
            equal = True
            while (nodes is not None):
                node: graph.Node = nodes.head
                out_nodes = self.out_node_table.get(node)
                gen_nodes = self.gen_node_table.get(node)
                in_nodes = self.in_node_table.get(node)
                kill_nodes = self.kill_node.get(node)
                if (not out_nodes == gen_nodes or not in_nodes == kill_nodes):
                    equal = False
                    break
                nodes = nodes.tail

        nodes = self.flowgraph.mynodes
        #Preenchemos o live_map
        while (nodes is not None):
            live: temp.TempList = temp.TempList()
            node: graph.Node = nodes.head
            for t in self.out_node_table.get(node):
                live.add_tail(t)
            self.live_map[node] = live
            nodes = nodes.tail



    def build_interference_graph(self):
        #Chamamos os métodos já definidos para preencher as arestas do grafo
        nodes: graph.NodeList = self.flowgraph.mynodes
        while (nodes is not None):
            node: graph.Node = nodes.head
            #Caso 1: nó é do tipo move
            if (self.flowgraph.is_move(node)):
                self.move_handler(node)
            #Caso 2: nó não é do tipo move
            else:
                self.node_handler(node)
            nodes = nodes.tail


class Edge():

    edges_table = {}

    def __init__(self):
        super.__init__()
    
    def get_edge(self, origin_node: graph.Node, destiny_node: graph.Node) -> Edge:
        
        origin_table = Edge.edges_table.get(origin_node)
        destiny_table = Edge.edges_table.get(destiny_node)
        
        if (origin_table is None):
            origin_table = {}
            Edge.edges_table[origin_node] = origin_table

        if (destiny_table is None):
            destiny_table = {}
            Edge.edges_table[destiny_node] = destiny_table
        
        requested_edge: Edge  = origin_table.get(destiny_node)

        if(requested_edge is None):
            requested_edge = Edge()
            origin_table[destiny_node] = requested_edge
            destiny_table[origin_node] = requested_edge

        return requested_edge



class MoveList():

   def __init__(self, s: graph.Node, d: graph.Node, t: MoveList):
      self.src: graph.Node = s
      self.dst: graph.Node = d
      self.tail: MoveList = t
