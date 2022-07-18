from __future__ import annotations
from abc import abstractmethod
import sys
from typing import Set
from pymjc.back import assem, flowgraph, graph
from pymjc.front import frame, temp


class RegAlloc (temp.TempMap):
    def __init__(self, frame: frame.Frame, instr_list: assem.InstrList):
        self.frame: frame.Frame = frame
        self.instrs: assem.InstrList = instr_list
        #TODO

    def temp_map(self, temp: temp.Temp) -> str:
        #TODO
        return temp.to_string()
    

class Color(temp.TempMap):
    def __init__(self, ig: InterferenceGraph, initial: temp.TempMap, registers: temp.TempList):
        #TODO
        pass
    
    def spills(self) -> temp.TempList:
        #TODO
        return None

    def temp_map(self, temp: temp.Temp) -> str:
        #TODO
        return temp.to_string()

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
