import pygame, traceback, math
import random, copy, socket
import pygame.gfxdraw

# Version 1.0 roadmap
# [x] add tombs (debug)
# [x] kill units when underpayed
# [x] add trees (debug)
# [x] tombs after a turn become trees
# [x] trees dont make income
# [x] tree spread
# [x] lone capital leaves tree
# [x] add done frame (debug)
# [x] add drag frame (debug)
# [x] add castles (debug)
# [x] ! test everything 1
# [x] add action queue
# [x] undo
# [x] victory condition
# [x] add lobby
# [x] add connection socket
# [x] add packet decode / encode
# [x] add action actuator
# [ ] finish art
# > [x] doode 0 idle
# > [x] doode 0 drag
# > [x] doode 0 done
# > [x] doode 1 idle
# > [x] doode 1 drag
# > [x] doode 1 done
# > [x] doode 2 idle
# > [x] doode 2 drag
# > [x] doode 2 done
# > [ ] doode 3 idle
# > [ ] doode 3 drag
# > [ ] doode 3 done
# > [x] town
# > [x] castle
# > [x] trees
# > [x] tombs
# [ ] sounds
# [ ] lobby track
# [ ] game track 0
# [ ] game track 1
# [x] add tile screen and decide name
# [x] optimization
# [ ] ! test everything 2s
# approx: 32 hrs. (spent: 1+3+2+3+3+3)
# work at least 3 hrs a day!!! -> the 18th finishline

# Test cases 1 (.: not done, -: ok, +: fixed)
# - money calculation
# - bankrupcy
# . tree spreading
# + strenght function
# - troubleshoot hover state machine
# - play a full game, look for bugs
# - trees stomping not working
# + banckrupcy was delayed 1 turn

# Optimizations
# - precalculate zones and neighbours
# . precalculate perimeter instead of each frame
# . precalculate order of tiles for unit blitting
# + render each zoom level separately and not each frame

class Opt:
    res = [800, 550]
    gamemode = 0
    lag = 100

class Loaded:
    imgs = []
    imgcolortile = []
    imgcolorhouse = []
    font = None
    fonttitle = None
    zoomimgs = []
    zoomcolorimgs = []
    zoomcolorhouse = []

class Tile:
    def __init__ (self):
        self.owner = 0; self.pos = [0, 0]
        self.grid = [0, 0]
        self.unit = None
        self.money = 0
        self.savings = 0
        self.income = 0
        self.upkeep = 0
        self.strenght = 0
        self.done = 0
        self.neighbours = []

class Player:
    color = [0,0,0]
    mind = 0

class Gamestate:
    players = []
    tiles = []
    sel = None
    perimetersel = []
    zoom = 0
    rel = [0, 0]
    turn = 0
    day = 0
    moves = []
    register = []
    hover = 0
    peerid = 0

class Commands:
    def __init__ (self):
        self.mousepos = [0, 0]
        self.mouse = [0, 0, 0]
        self.pressed = [0, 0, 0]
        self.wheel = 0
        self.relwheel = 0
        self.relpos = [0, 0]
        self.keysdown = []
        self.res = [0, 0]

    def update (self):
        self.keysdown = []
        for i in range(3):
            if pygame.mouse.get_pressed()[i]: self.mouse[i] += 1
            elif self.mouse[i] > 0: self.mouse[i] = -1
            else: self.mouse[i] = 0
        self.pressed = pygame.mouse.get_pressed()

        mx, my = pygame.mouse.get_pos()
        self.relpos = [mx-self.mousepos[0], my-self.mousepos[1]]
        self.mousepos = [mx, my]
        
        self.relwheel = 0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                self.keysdown += [pygame.key.name(e.key)]
                if e.key == pygame.K_ESCAPE:
                    return False
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 4:
                    self.wheel += 1
                    self.relwheel = 1
                elif e.button == 5:
                    self.wheel -= 1
                    self.relwheel = -1
            if e.type == pygame.VIDEORESIZE:
                self.res = e.size
        return True

class LocalPeer:
    def __init__ (self):
        self.id = 0
        self.lobbycolorangle = 0
        self.localplayers = []
        self.hostplayers = []
        self.hostSock = None
        self.clientSock = None
        self.foundhosts = []
        self.act = None
        self.hostAddr = None
        self.requestqueue = []
        self.start = 0
        self.mapseed = 0
        self.mapsize = 0
        self.mapindex = 0
        self.passedturn = False
        self.packettimer = 0
        self.turnmoves = []

class Move:
    def __init__ (self):
        self.selector = 0
        self.gridposstart = 0
        self.gridposend = 0
        self.player = 0
        self.day = 0
        self.snapshot = None
 
class Action:
    def __init__ (self, protocol):
        self.protocol = protocol
        self.playernum = 0
        self.starting = 0
        self.color_r = 0
        self.color_g = 0
        self.color_b = 0
        self.playerindex = 0
        self.mapseed = 0
        self.mapsize = 0
        self.mapindex = 0
        self.registerlenght = 0
        self.movesstart = 0
        self.movesend = 0
        self.moves = []
    def __repr__ (self):
        return "[Action: protocol: "+str(self.protocol)+"]"
        
def act_encode (act):
    b = bytes();
    b += (act.protocol).to_bytes(1, byteorder='big')
    if act.protocol == 0: # request connection
        b += (act.color_r).to_bytes(1, byteorder='big')
        b += (act.color_g).to_bytes(1, byteorder='big')
        b += (act.color_b).to_bytes(1, byteorder='big')
        return b
    if act.protocol == 1: # accept connection
        b += (act.playerindex).to_bytes(1, byteorder='big')
        return b
    if act.protocol == 2: # lobby general request
        return b
    if act.protocol == 3: # lobby set
        b += (act.playernum).to_bytes(1, byteorder='big')
        b += (act.starting).to_bytes(1, byteorder='big')
        b += (act.mapseed).to_bytes(4, byteorder='big')
        b += (act.mapsize).to_bytes(4, byteorder='big')
        b += (act.mapindex).to_bytes(4, byteorder='big')
        return b
    if act.protocol == 4: # lobby playerinfo request
        b += (act.playerindex).to_bytes(1, byteorder='big')
        return b
    if act.protocol == 5: # lobby playerinfo set
        b += (act.playerindex).to_bytes(1, byteorder='big')
        b += (act.color_r).to_bytes(1, byteorder='big')
        b += (act.color_g).to_bytes(1, byteorder='big')
        b += (act.color_b).to_bytes(1, byteorder='big')
        return b
    if act.protocol == 6: # general request
        return b
    if act.protocol == 7: # general response
        b += (act.registerlenght).to_bytes(4, byteorder='big')
        return b
    if act.protocol == 8: # request moves
        b += (act.movesstart).to_bytes(4, byteorder='big')
        b += (act.movesend).to_bytes(4, byteorder='big')
        return b
    if act.protocol == 9: # moves set
        b += (act.movesstart).to_bytes(4, byteorder='big')
        b += (act.movesend).to_bytes(4, byteorder='big')
        for i in range(len(act.moves)): # 11 bytes
            b += (act.moves[i].selector).to_bytes(1, byteorder='big')
            b += (act.moves[i].gridposstart).to_bytes(4, byteorder='big')
            b += (act.moves[i].gridposend).to_bytes(4, byteorder='big')
            b += (act.moves[i].player).to_bytes(1, byteorder='big')
            b += (act.moves[i].day).to_bytes(1, byteorder='big')
        return b
    if act.protocol == 10: # moves ack
        return b
    
def act_decode (b):
    act = Action(int.from_bytes(b[0:1], byteorder='big'))
    if act.protocol == 0:
        act.color_r = int.from_bytes(b[1:2], byteorder='big')
        act.color_g = int.from_bytes(b[2:3], byteorder='big')
        act.color_b = int.from_bytes(b[3:4], byteorder='big')
    if act.protocol == 1:
        act.playerindex = int.from_bytes(b[1:2], byteorder='big')
    if act.protocol == 3:
        act.playernum = int.from_bytes(b[1:2], byteorder='big')
        act.starting = int.from_bytes(b[2:3], byteorder='big')
        act.mapseed = int.from_bytes(b[3:7], byteorder='big')
        act.mapsize = int.from_bytes(b[7:11], byteorder='big')
        act.mapindex = int.from_bytes(b[11:15], byteorder='big')
    if act.protocol == 4:
        act.playerindex = int.from_bytes(b[1:2], byteorder='big')
    if act.protocol == 5:
        act.playerindex = int.from_bytes(b[1:2], byteorder='big')
        act.color_r = int.from_bytes(b[2:3], byteorder='big')
        act.color_g = int.from_bytes(b[3:4], byteorder='big')
        act.color_b = int.from_bytes(b[4:5], byteorder='big')
    if act.protocol == 7:
        act.registerlenght = int.from_bytes(b[1:5], byteorder='big')
    if act.protocol == 8:
        act.movesstart = int.from_bytes(b[1:5], byteorder='big')
        act.movesend = int.from_bytes(b[5:9], byteorder='big')
    if act.protocol == 9:
        act.movesstart = int.from_bytes(b[1:5], byteorder='big')
        act.movesend = int.from_bytes(b[5:9], byteorder='big')
        print(act.movesstart)
        print(act.movesend)
        lenght = act.movesend - act.movesstart
        for i in range(lenght):
            move = Move()
            st = 9+11*i
            move.selector = int.from_bytes(b[st:st+1], byteorder='big')
            move.gridposstart = int.from_bytes(b[st+1:st+5], byteorder='big')
            move.gridposend = int.from_bytes(b[st+5:st+9], byteorder='big')
            move.player = int.from_bytes(b[st+9:st+10], byteorder='big')
            move.day = int.from_bytes(b[st+10:st+11], byteorder='big')
            act.moves.append(move)
            print(move.selector, move.gridposstart, move.gridposend, move.player, move.day)
        print("end")
    return act


def hsv_to_rgb (h, s=1, v=1):
    c = v*s
    x = c*(1-abs((h/60.0)%2-1))
    m = v - c
    if 0 <= h < 60: a = (c, x, 0)
    if 60 <= h < 120: a = (x, c, 0)
    if 120 <= h < 180: a = (0, c, x)
    if 180 <= h < 240: a = (0, x, c)
    if 240 <= h < 300: a = (x, 0, c)
    if 300 <= h <= 360: a = (c, 0, x)
    return int((a[0]+m)*255), int((a[1]+m)*255), int((a[2]+m)*255)

def calc_good_mapsize (size):
    c = 1; i = 0
    while True:
        if c == size: return True
        if c > size: return False
        c += 6*i; i += 1

def get_next_mapsize (size):
    c = 1; i = 0
    while True:
        if c+6*i > size: return c+6*i
        c += 6*i; i += 1

def get_prev_mapsize (size):
    c = 1; i = 0
    while True:
        if c+6*i > size: return c-6*(i-1)
        c += 6*i; i += 1

def abs_to_zoom (pos, rel, zoom, res):
    z = (zoom*0.1)+1
    zinverse = 1/z

    rnp = [pos[0]+rel[0], pos[1]+rel[1]]
    rnp = [rnp[0]*z, rnp[1]*z]
    rnp = [rnp[0]+(res[0]/2)*(1-z), rnp[1]+(res[1]/2)*(1-z)]
    return rnp

def zoom_to_abs (pos, rel, zoom, res):
    z = (zoom*0.1)+1
    zinverse = 1/z

    rnp = [pos[0]-(res[0]/2)*(1-z), pos[1]-(res[1]/2)*(1-z)]
    rnp = [rnp[0]*zinverse, rnp[1]*zinverse]
    rnp = [rnp[0]-rel[0], rnp[1]-rel[1]]
    return rnp

def get_neighbours (gst, index):
    if index == None: return []
    return gst.tiles[index].neighbours

def prec_get_neighbours (gst, index):
    ret = []
    neigh = [
        [1, 0],
        [0, 1],
        [-1, 1],
        [-1, 0],
        [0, -1],
        [1, -1],
    ]
    for j in range(len(neigh)):
        nx = gst.tiles[index].grid[0]+neigh[j][0]
        ny = gst.tiles[index].grid[1]+neigh[j][1]
        for i in range(len(gst.tiles)):
            if nx == gst.tiles[i].grid[0] and \
                    ny == gst.tiles[i].grid[1]:
                ret.append(i)
    return ret

def get_zone (gst, index):
    if index == None: return []
    grid = gst.tiles[index].grid
    zone = [index]
    queue = [index]
    while True:
        s = zone[0]
        zone = zone[1:]
        friends = get_neighbours(gst, s)
        for f in friends:
            if not(f in queue or f in zone) and \
                   gst.tiles[f].owner == gst.tiles[index].owner:
                zone.append(f)
        if len(zone) == 0: return queue
        queue += [zone[0]]

def get_borders (gst, index):
    zone = get_zone(gst, index)
    border = []
    for z in zone:
        neigh = get_neighbours(gst, z)
        for n in neigh:
            if not(n in border): border += [n]
    return border

def get_perimeter(gst, zone):
    neigh = [
        [1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1],
    ]
    perimeter = []
    for i in zone:
        for j in range(len(neigh)):
            nx = gst.tiles[i].grid[0]+neigh[j][0]
            ny = gst.tiles[i].grid[1]+neigh[j][1]
            for s in range(len(gst.tiles)):
                if nx == gst.tiles[s].grid[0] and \
                        ny == gst.tiles[s].grid[1] and \
                        gst.tiles[i].owner != gst.tiles[s].owner:
                    perimeter += [[i, (j+4)%6]]
    return perimeter

def get_capital (gst, index):
    zone = get_zone(gst, index)
    for i in zone:
        if gst.tiles[i].unit == 1: return i
    return index

def calculate_income (gst, index):
    zone = get_zone(gst, index)
    income = 0
    for z in zone:
        if gst.tiles[z].unit != 3: income += 1
    return income

def calculate_upkeep (gst, index):
    zone = get_zone(gst, index)
    upkeep_to_strenght = [0, 2, 6, 18, 52]
    upkeep = 0
    for z in zone:
        if gst.tiles[z].unit == 0:
            upkeep += upkeep_to_strenght[gst.tiles[z].strenght]
    return upkeep

def calculate_balance (gst, index):
    capital = get_capital(gst, index)
    income = gst.tiles[index].income
    upkeep = gst.tiles[index].upkeep
    return gst.tiles[capital].savings + income - upkeep

def calculate_bankrupcy (gst, index):
    if calculate_balance(gst, index) < 0:
        capital = get_capital(gst, index)
        gst.tiles[capital].savings = 0
        zone = get_zone(gst, index)
        for z in zone:
            if gst.tiles[z].unit == 0:
                gst.tiles[z].unit = 2
                gst.tiles[z].strenght = 0
                gst.tiles[z].done = 0

def calculate_victory (gst):
    count = [0 for i in range(0, len(gst.players))]
    for i in range(len(gst.tiles)):
        count[gst.tiles[i].owner] += 1
    for i in range(len(count)):
        if count[i] == len(gst.tiles):
            return i
    return None

def calculate_ply(gst, player, trees):
    capitals = []
    for i in range(len(gst.tiles)):
        tile = gst.tiles[i]
        if gst.tiles[i].owner == player:
            if gst.tiles[i].unit == 2 and trees:
                # tombs become trees
                gst.tiles[i].unit = 3
            gst.tiles[i].done = 0
            capital = get_capital(gst, i)
            if not(capital in capitals):
                capitals += [capital]
    if gst.day > 0:
        for c in capitals:
            gst.tiles[c].savings = gst.tiles[c].money
            gst.tiles[c].upkeep = calculate_upkeep(gst, c)
            gst.tiles[c].income = calculate_income(gst, c)
            gst.tiles[c].money = calculate_balance(gst, c)
            calculate_bankrupcy(gst, c)
    calculate_tree_spread(gst)

def calculate_next_ply(gst):
    gst.turn += 1
    if gst.turn>=len(gst.players):
        gst.turn = 0
        gst.day += 1

    # victory
    victory = calculate_victory(gst)
    if victory != None:
        print(str(victory)+" won!")
    calculate_ply (gst, gst.turn, True)

def calculate_defence (gst, index):
    neighs = get_neighbours(gst, index)
    strenghts = [gst.tiles[index].strenght]
    for n in neighs:
        if gst.tiles[n].owner == gst.tiles[index].owner:
            strenghts += [gst.tiles[n].strenght]
    return max(strenghts)

def calculate_attack (gst, strenght, defender):
    if strenght > calculate_defence(gst, defender): return True
    return False

def calculate_tree_spread (gst):
    # if an empty tile has 2 tree neighs -> tree
    new = []
    for i in range(0, len(gst.tiles)):
        if gst.tiles[i].unit == None:
            neighs = get_neighbours(gst, i)
            count = 0
            for n in neighs:
                if gst.tiles[n].unit == 3: count += 1
            if count >= 2: new += [i]
    for i in new:
        gst.tiles[i].unit = 3

def update_capital (gst, index):
    zone = get_zone(gst, index)
    capitals = []
    for i in zone:
        if gst.tiles[i].unit == 1: capitals += [i]
    if len(capitals) == 0:
        available_spots = []
        for i in zone:
            if not(gst.tiles[i].unit in [0]): available_spots += [i]
        if len(available_spots) > 1:
            capital = random.choice(available_spots)
            gst.tiles[capital].unit = 1
            gst.tiles[capital].strenght = 1
            gst.tiles[capital].savings = 0
            gst.tiles[capital].money = 0
            gst.tiles[capital].income = calculate_income(gst, capital)
            gst.tiles[capital].upkeep = calculate_upkeep(gst, capital)
    if len(capitals) >= 2:
        best = max(capitals, key=lambda x: gst.tiles[x].savings)
        for i in capitals:
            if i != best:
                gst.tiles[best].money += gst.tiles[i].money
                gst.tiles[best].upkeep += gst.tiles[i].upkeep
                gst.tiles[best].income += gst.tiles[i].income
                gst.tiles[i].savings = 0
                gst.tiles[i].money = 0
                gst.tiles[i].strenght = 0
                gst.tiles[i].unit = None
                gst.tiles[i].income = 0
                gst.tiles[i].upkeep = 0
    if len(zone) == 1 and len(capitals) == 1:
        gst.tiles[index].unit = 3
        gst.tiles[index].savings = 0
        gst.tiles[index].strenght = 0
        gst.tiles[index].money = 0
        gst.tiles[index].done = 0
        gst.tiles[i].income = 0
        gst.tiles[i].upkeep = 0

def add_move (gst, sel, a, b, player, day):
    move = Move()
    move.selector = sel
    move.gridposstart = a
    move.gridposend = b
    move.player = player
    move.day = day
    move.snapshot = copy.deepcopy(gst.tiles)
    gst.moves.append(move)

def actuate (gst, moves):
    for move in moves:
        if move.selector == 0:
            unit_place(gst, move.gridposstart, move.gridposend)
        if move.selector == 1:
            unit_place_castle(gst, move.gridposend)
        if move.selector == 2:
            unit_new_upgrade(gst, move.gridposend)
        if move.selector == 3:
            unit_new_attack(gst, move.gridposstart, move.gridposend)
        if move.selector == 4:
            unit_move(gst, move.gridposstart, move.gridposend)
        if move.selector == 5:
            unit_upgrade(gst, move.gridposstart, move.gridposend)
        if move.selector == 6:
            unit_attack(gst, move.gridposstart, move.gridposend)
        if move.selector == 7:
            calculate_next_ply(gst)

def unit_place (gst, prev, index):
    # selector = 0
    gst.tiles[index].unit = 0
    gst.tiles[index].strenght = 1
    gst.tiles[get_capital(gst, index)].money -= 10
    
def unit_place_castle (gst, index):
    # selector = 1
    gst.tiles[index].unit = 4
    gst.tiles[index].strenght = 2
    gst.tiles[get_capital(gst, index)].money -= 15

def unit_new_upgrade (gst, index):
    # selector = 2
    gst.tiles[index].strenght += 1
    gst.tiles[get_capital(gst, index)].money -= 10

def unit_new_attack (gst, prev, index):
    # selector = 3
    gst.tiles[index].unit = 0
    gst.tiles[index].strenght = 1
    gst.tiles[index].done = 1
    gst.tiles[index].owner = gst.tiles[prev].owner
    neighs = get_neighbours(gst, index)
    for n in neighs: update_capital(gst, n)
    gst.tiles[get_capital(gst, index)].money -= 10

def unit_move (gst, prev, index):
    # selector = 4
    gst.tiles[index].unit = gst.tiles[prev].unit
    gst.tiles[index].strenght = gst.tiles[prev].strenght
    gst.tiles[prev].unit = None
    gst.tiles[prev].strenght = 0

def unit_upgrade (gst, prev, index):
    # selector = 5
    gst.tiles[index].strenght += gst.tiles[prev].strenght
    gst.tiles[prev].unit = None
    gst.tiles[prev].strenght = 0
    
def unit_attack (gst, prev, index):
    # selector = 6
    gst.tiles[index].savings = 0
    gst.tiles[index].upkeep = 0
    gst.tiles[index].income = 0
    gst.tiles[index].money = 0
    gst.tiles[index].unit = gst.tiles[prev].unit
    gst.tiles[index].strenght = gst.tiles[prev].strenght
    gst.tiles[index].done = 1
    gst.tiles[index].owner = gst.tiles[prev].owner
    neighs = get_neighbours(gst, index)
    for n in neighs: update_capital(gst, n)
    gst.tiles[prev].unit = None
    gst.tiles[prev].strenght = 0
    gst.tiles[prev].done = 0

def reset_sel (gst, prev):
    gst.sel = prev
    gst.perimetersel = get_perimeter(gst, get_zone(gst, gst.sel))

def proc_unit_place (gst, prev):
    prevzone = get_zone(gst, prev)
    border = get_borders(gst, prev)
    if gst.sel in border:
        if gst.sel in prevzone:
            if gst.tiles[gst.sel].unit in [None, 2, 3]:
                add_move(gst, 0, prev, gst.sel, gst.turn, gst.day)
                unit_place(gst, prev, gst.sel)
            elif gst.tiles[gst.sel].unit == 0:
                add_move(gst, 2, 0, gst.sel, gst.turn, gst.day)
                unit_new_upgrade(gst, gst.sel)
            else: reset_sel(gst, prev)
        elif gst.sel in border:
            if calculate_attack(gst, 1, gst.sel):
                add_move(gst, 3, prev, gst.sel, gst.turn, gst.day)
                unit_new_attack(gst, prev, gst.sel)
            else: reset_sel(gst, prev)
        else: reset_sel(gst, prev)
    else: reset_sel(gst, prev)
    gst.hover = 0
    gst.perimetersel = get_perimeter(gst, get_zone(gst, gst.sel))

def proc_unit_place_castle (gst, prev):
    prevzone = get_zone(gst, prev)
    if gst.sel in prevzone:
        if gst.tiles[gst.sel].unit == None:
            add_move(gst, 1, 0, gst.sel, gst.turn, gst.day)
            unit_place_castle(gst, gst.sel)
        else: reset_sel(gst, prev)
    else: reset_sel(gst, prev)
    gst.hover = 0
    gst.perimetersel = get_perimeter(gst, get_zone(gst, gst.sel))

def proc_unit_move (gst, prev):
    if gst.sel == prev: gst.sel = None; gst.hover = 0
    prevzone = get_zone(gst, prev)
    border = get_borders(gst, prev)
    if gst.sel in border:
        if gst.sel in prevzone:
            if gst.tiles[gst.sel].unit in [None, 2, 3]:
                add_move(gst, 4, prev, gst.sel, gst.turn, gst.day)
                unit_move (gst, prev, gst.sel)
            elif gst.tiles[gst.sel].unit == 0:
                add_move(gst, 5, prev, gst.sel, gst.turn, gst.day)
                unit_upgrade (gst, prev, gst.sel)
            else: reset_sel(gst, prev)
        elif gst.sel in border:
            if calculate_attack(gst, gst.tiles[prev].strenght, gst.sel):
                add_move(gst, 6, prev, gst.sel, gst.turn, gst.day)
                unit_attack(gst, prev, gst.sel)
            else: reset_sel(gst, prev)
        else: reset_sel(gst, prev)
    else: reset_sel(gst, prev)
    gst.hover = 0
    gst.perimetersel = get_perimeter(gst, get_zone(gst, gst.sel))
        
def process(scr, com, gst, loaded, opt, acc, peer):
    if peer.hostSock != None:
        net_host_process(gst, opt, peer)
    if peer.clientSock != None:
        net_client_process(gst, opt, peer, acc)
        
    z = (gst.zoom*0.1)+1
    zinverse = 1/z
    if com.mouse[2] > 1:
        gst.rel[0] += com.relpos[0]*zinverse
        gst.rel[1] += com.relpos[1]*zinverse
    gst.zoom += com.relwheel
    if gst.zoom <= -5:
        gst.zoom = -5
    if gst.zoom > 0:
        gst.zoom = 0

    if opt.gamemode == 1 and peer.id != gst.turn: return

    if com.mouse[0] == 1:
        if com.mousepos[0]<opt.res[0]-200:
            nearest = -1; dist = 999999
            prev = gst.sel
            for i in range(0, len(gst.tiles)):
                tile = gst.tiles[i]
                abspos = zoom_to_abs(com.mousepos, gst.rel, gst.zoom, opt.res)
                xx = tile.pos[0]-abspos[0]
                yy = tile.pos[1]-abspos[1]
                candist = math.sqrt(xx*xx+yy*yy)
                if candist < dist:
                    nearest = i
                    dist = candist
            if nearest != -1:
                gst.sel = nearest
                gst.perimetersel = get_perimeter(gst, get_zone(gst, gst.sel))
            # additional validation
            if dist > 40: gst.sel = None; gst.perimetersel = []
            
            if gst.hover == 1:
                proc_unit_place(gst, prev)
            elif gst.hover == 2:
                proc_unit_move(gst, prev)
            elif gst.hover == 3:
                proc_unit_place_castle(gst, prev)
            else: 
                zone = get_zone(gst, gst.sel)
                if len(zone) <= 1 or gst.tiles[gst.sel].owner != gst.turn:
                    gst.sel = None; gst.perimetersel = []
                if gst.sel != None:
                    if gst.tiles[gst.sel].unit == 0 and \
                            gst.tiles[gst.sel].done == 0 :
                        gst.hover = 2
        else:
            if com.mousepos[1]>170-80 and com.mousepos[1]<170 and \
               com.mousepos[0]<opt.res[0]-100:
                capital = get_capital(gst, gst.sel)
                money = gst.tiles[capital].money
                if money >= 10:
                    gst.hover = 1
            elif com.mousepos[1]>170-80 and com.mousepos[1]<170 and \
               com.mousepos[0]<opt.res[0]:
                capital = get_capital(gst, gst.sel)
                money = gst.tiles[capital].money
                if money >= 15:
                    gst.hover = 3
            if com.mousepos[1]>opt.res[1]-100:
                calculate_next_ply(gst)
                
                newturnmove = Move()
                newturnmove.selector = 7
                gst.moves += [newturnmove]
                gst.register += gst.moves
                if opt.gamemode == 1:
                    peer.passedturn = True
                    peer.turnmoves = copy.deepcopy(gst.moves)
                del gst.moves[:]
                
                gst.hover = 0
                gst.sel = None; gst.perimetersel = []

    if "z" in com.keysdown:
        if len(gst.moves) > 0:
            gst.tiles = copy.deepcopy(gst.moves[-1].snapshot)
            gst.moves = gst.moves[:-1]
            gst.sel = None; gst.perimetersel = []
            gst.hover = 0


def render_sidebar (scr, gst, loaded, opt):
    pygame.draw.rect(scr, (220, 220, 220),
        (opt.res[0]-200, 0, opt.res[0], opt.res[1]))
    pygame.draw.rect(scr, (0, 0, 0),
        (opt.res[0]-200, -1, opt.res[0]+1, opt.res[1]+1), 1)

    # graphs
    pygame.draw.rect(scr, (240, 240, 240),
        (opt.res[0]-200, opt.res[1]-300, 200, 200))
    pygame.draw.rect(scr, (0, 0, 0),
        (opt.res[0]-200, opt.res[1]-300, opt.res[0]+1, 201), 1)
    pygame.draw.line(scr, (0, 0, 0),
        (opt.res[0]-190, opt.res[1]-110),
        (opt.res[0]-16, opt.res[1]-110))
    playercounts = [0 for i in range(len(gst.players))]
    for i in range(0,len(gst.players)):
        for tile in gst.tiles:
            if tile.owner == i: playercounts[i] += 1
    for i in range(0,len(gst.players)):
        amt = (playercounts[i]/max(playercounts))*180
        width = 180/len(gst.players)
        pygame.draw.rect(scr, gst.players[i].color,
            (opt.res[0]-190+i*width, opt.res[1]-111,
             width-5, -amt))

    # end turn
    pygame.draw.rect(scr, (255, 255, 255),
        (opt.res[0]-200, opt.res[1]-100, 200, 100))
    pygame.draw.rect(scr, (0, 0, 0),
        (opt.res[0]-200, opt.res[1]-100, opt.res[0]+1, 101), 1)
    
    scr.blit(loaded.font.render("PASS TURN", 4, (0, 0, 0)),
        (opt.res[0]-190, opt.res[1]-90))
    
    scr.blit(loaded.font.render("TURN: "+str(gst.turn), 4, (0, 0, 0)),
        (opt.res[0]-190, opt.res[1]-70))
    scr.blit(loaded.font.render("DAY: "+str(gst.day), 4, (0, 0, 0)),
        (opt.res[0]-190, opt.res[1]-50))

def render_sidebar_town(scr, gst, loaded, opt):
    if gst.sel == None: return
    zone = get_zone(gst, gst.sel)
    capital = get_capital(gst, gst.sel)
    pygame.draw.rect(scr, (255, 255, 255),
        (opt.res[0]-200, 0, opt.res[0], 190))
    pygame.draw.rect(scr, (0, 0, 0),
        (opt.res[0]-200, -1, opt.res[0]+1, 191), 1)
    income = gst.tiles[capital].income
    scr.blit(loaded.font.render("SAVINGS: "+str(gst.tiles[capital].savings), \
        4, (0, 0, 0)), (opt.res[0]-190, 10))
    scr.blit(loaded.font.render("INCOME: "+str(income), 4, (0, 0, 0)),
        (opt.res[0]-190, 28))
    upkeep = gst.tiles[capital].upkeep
    scr.blit(loaded.font.render("UPKEEP: "+str(-upkeep), 4, (0, 0, 0)),
        (opt.res[0]-190, 46))
    balance = calculate_balance(gst, capital)
    scr.blit(loaded.font.render("BALANCE: "+str(balance), 4, (0, 0, 0)),
        (opt.res[0]-190, 64))
    money = gst.tiles[capital].money
    scr.blit(loaded.font.render("MONEY: "+str(money), 4, (0, 0, 0)),
        (opt.res[0]-190, 82))

    for i in range(0, min(7, int(money/10)-int(gst.hover==1))):
        scr.blit(loaded.imgs[7], (opt.res[0]-170-80+i*7, 170-80))
        
    for i in range(0, min(7, int(money/15)-int(gst.hover==3))):
        scr.blit(loaded.imgs[22], (opt.res[0]-70-80+i*7, 170-80))
    
def render_map(scr, gst, loaded, opt):
    z = (gst.zoom*0.1)+1
    zinverse = 1/z
    zindex = gst.zoom+5
    
    neighs = get_neighbours(gst, gst.sel)
    zone = get_zone(gst, gst.sel)
    per = gst.perimetersel
    
    for i in range(len(gst.tiles)):
        tile = gst.tiles[i]
        size = int(70*z), int(70*z)
        
        pos = tile.pos[0]-size[0]/2*zinverse, tile.pos[1]-size[1]/2*zinverse
        pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        if i in zone:
            scr.blit(loaded.zoomcolorimgs[tile.owner+len(gst.players)][zindex], pos)
        else:
            scr.blit(loaded.zoomcolorimgs[tile.owner][zindex], pos)
    for i, j in per:
        tile = gst.tiles[i]
        size = int(70*z), int(70*z)
        
        pos = tile.pos[0]-size[0]/2*zinverse, tile.pos[1]-size[1]/2*zinverse
        pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        
        scr.blit(loaded.zoomimgs[j+1][zindex], pos)
        
    ordtiles = sorted(gst.tiles, key=lambda x: x.grid[1], reverse=True)
    for i in range(len(ordtiles)):
        tile = ordtiles[i]
        size = int(160*z), int(160*z)
        
        pos = tile.pos[0]-size[0]/2*zinverse, tile.pos[1]-size[1]/2*zinverse
        pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        if tile.unit == 0:
            if not(gst.hover == 2 and gst.tiles[gst.sel].grid == tile.grid):
                img = 7+(tile.strenght-1)*3
                img += int(tile.done==1)*2
                scr.blit(loaded.zoomimgs[img][zindex], pos)
        if tile.unit == 1:
            scr.blit(loaded.zoomimgs[19][zindex], pos)
            scr.blit(loaded.zoomcolorhouse[tile.owner][zindex], pos)
        if tile.unit == 2:
            scr.blit(loaded.zoomimgs[20][zindex], pos)
        if tile.unit == 3:
            scr.blit(loaded.zoomimgs[21][zindex], pos)
        if tile.unit == 4:
            scr.blit(loaded.zoomimgs[22][zindex], pos)

def render_hover (scr, gst, loaded, opt, com):
    z = (gst.zoom*0.1)+1
    zinverse = 1/z
    if gst.hover == 1:
        if com.mousepos[0] > opt.res[0]-200:
            size = int(160), int(160)
            pos = com.mousepos[0]-size[0]/2, com.mousepos[1]-size[1]/2
        else:
            size = int(160*z), int(160*z)
            abspos = zoom_to_abs(com.mousepos, gst.rel, gst.zoom, opt.res)
            pos = abspos[0]-size[0]/2*(zinverse), \
                  abspos[1]-size[1]/2*(zinverse)
            pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        new = pygame.transform.smoothscale(loaded.imgs[7+1], size)
        scr.blit(new, pos)
        
    if gst.hover == 2:
        if com.mousepos[0] > opt.res[0]-200:
            size = int(160), int(160)
            pos = com.mousepos[0]-size[0]/2, com.mousepos[1]-size[1]/2
        else:
            size = int(160*z), int(160*z)
            abspos = zoom_to_abs(com.mousepos, gst.rel, gst.zoom, opt.res)
            pos = abspos[0]-size[0]/2*(zinverse),\
                  abspos[1]-size[1]/2*(zinverse)
            pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        new = pygame.transform.smoothscale(
            loaded.imgs[7+(gst.tiles[gst.sel].strenght-1)*3+1], size)
        scr.blit(new, pos)
        
    if gst.hover == 3:
        if com.mousepos[0] > opt.res[0]-200:
            size = int(160), int(160)
            pos = com.mousepos[0]-size[0]/2, com.mousepos[1]-size[1]/2
        else:
            size = int(160*z), int(160*z)
            abspos = zoom_to_abs(com.mousepos, gst.rel, gst.zoom, opt.res)
            pos = abspos[0]-size[0]/2*(zinverse),\
                  abspos[1]-size[1]/2*(zinverse)
            pos = abs_to_zoom(pos, gst.rel, gst.zoom, opt.res)
        new = pygame.transform.smoothscale(
            loaded.imgs[22], size)
        scr.blit(new, pos)

def render(scr, com, gst, loaded, opt, acc, peer):
    render_map(scr, gst, loaded, opt)
    render_sidebar(scr, gst, loaded, opt)
    render_sidebar_town(scr, gst, loaded, opt)
    render_hover(scr, gst, loaded, opt, com)
    pygame.display.flip()
    scr.fill((30, 30, 30))

def create_map (gst, size, off):
    norm = lambda g: [g[0], g[1]]
    
    gst.tiles = list()
    sequence = list()
    ts = 54
    c, s = [math.cos(math.pi/3)*ts, math.sin(math.pi/3)*ts]
    direction = [
        [ts, 0],
        [c, -s],
        [-c, -s],
        [-ts, 0],
        [-c, s],
        [c, s],
    ]
    # z = x - y
    griddir = [
        [1, 0],
        [0, 1],
        [-1, 1],
        [-1, 0],
        [0, -1],
        [1, -1],
    ]
    
    t=1; e=0; f=2
    for i in range(0, size):
        if e>=t*6: t+=1; e=0; f=1
        if e==0: sequence += [0]
        else:
            sequence += [f%6]
            if e%t==t-1: f+=1
        e+=1
    pos = [off[0], off[1]]
    grid = [0, 0]
    for i in range(0, size):
        tile = Tile()
        tile.owner = random.randint(0, len(gst.players)-1)
        tile.pos[0] = pos[0]
        tile.pos[1] = pos[1]
        tile.grid = norm(grid)
        gst.tiles.append(tile)
        pos[0] += direction[sequence[i]][0]
        pos[1] += direction[sequence[i]][1]
        grid[0] += griddir[sequence[i]][0]
        grid[1] += griddir[sequence[i]][1]

    # precalculate neighbours
    for i in range(0, size):
        gst.tiles[i].neighbours = prec_get_neighbours(gst, i)

    # populate map
    for i in range(0, size):
        tile = gst.tiles[i]
        zone = get_zone(gst, i)
        flag = True
        for z in zone:
            if gst.tiles[z].unit == 1: flag = False
        if flag and len(zone)>1:
            capital = random.choice(zone)
            gst.tiles[capital].unit = 1
            gst.tiles[capital].strenght = 1
            gst.tiles[capital].savings = 8
            gst.tiles[capital].upkeep = 0
            gst.tiles[capital].income = calculate_income(gst, capital)
            gst.tiles[capital].money = calculate_balance(gst, capital)

def color_img (img, color):
    new = pygame.Surface(img.get_size()).convert_alpha()  
    new.fill((color[0], color[1], color[2], 255))
    new.blit(img, (0,0), None, pygame.BLEND_RGBA_MIN)
    #new.fill((color[0], color[1], color[2], 0), None, pygame.BLEND_RGBA_ADD)
    return new

def refresh_zoom (loaded, gst):
    del loaded.zoomimgs[:]
    del loaded.zoomcolorimgs[:]
    del loaded.zoomcolorhouse[:]
    zooms = []
    for i in range(-5, 1):
        z = (i*0.1)+1
        zinverse = 1/z
        zooms += [z]
    # units
    for i in range(0, len(loaded.imgs)):
        loaded.zoomimgs += [[]]
        for zoom in zooms:
            oldsize = loaded.imgs[i].get_size()
            size = int(oldsize[0]*zoom), int(oldsize[1]*zoom)
            new = pygame.transform.smoothscale(loaded.imgs[i], size)
            loaded.zoomimgs[-1] += [new]
    # tiles
    for imgtile in loaded.imgcolortile:
        loaded.zoomcolorimgs += [[]]
        for zoom in zooms:
            oldsize = imgtile.get_size()
            size = int(oldsize[0]*zoom), int(oldsize[1]*zoom)
            new = pygame.transform.smoothscale(imgtile, size)
            loaded.zoomcolorimgs[-1] += [new] 
    # houses
    size = int(160*z), int(160*z)
    for imghouse in loaded.imgcolorhouse:
        loaded.zoomcolorhouse += [[]]
        for zoom in zooms:
            oldsize = imghouse.get_size()
            size = int(oldsize[0]*zoom), int(oldsize[1]*zoom)
            new = pygame.transform.smoothscale(imghouse, size)
            loaded.zoomcolorhouse[-1] += [new]

def refresh_colors (loaded, gst):
    del loaded.imgcolortile[:]
    for pl in gst.players:
        loaded.imgcolortile.append(color_img(loaded.imgs[0], pl.color))
    for pl in gst.players:
        col = [(pl.color[i]+256)/2 for i in range(3)]
        loaded.imgcolortile.append(color_img(loaded.imgs[0], col))
    for pl in gst.players:
        col = [(pl.color[i]+128)/2 for i in range(3)]
        loaded.imgcolorhouse.append(color_img(loaded.imgs[23], col))

def load (loaded):
    loaded.imgs.append(pygame.image.load("./imgs/hex.png").convert_alpha())
    for i in range(6):
        loaded.imgs.append(pygame.image.load(
            "./imgs/hexframe"+str(i+1).zfill(4)+".png").convert_alpha())
    for i in range(4):
        loaded.imgs.append(pygame.image.load(
            "./imgs/doode"+str(i).zfill(4)+"idle.png").convert_alpha())
        loaded.imgs.append(pygame.image.load(
            "./imgs/doode"+str(i).zfill(4)+"drag.png").convert_alpha())
        loaded.imgs.append(pygame.image.load(
            "./imgs/doode"+str(i).zfill(4)+"done.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/house.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/tomb.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/tree.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/castle.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/housecolor.png").convert_alpha())
    loaded.imgs.append(pygame.image.load("./imgs/photo.png").convert_alpha())
    loaded.font = pygame.font.Font("./cont/OpenSans-Light.ttf", 18)
    loaded.fonttitle = pygame.font.Font("./cont/OpenSans-Light.ttf", 36)

def generate_request (gst, opt, peer):
    act = Action(6)
    if len(peer.requestqueue) > 0:
        act = peer.requestqueue[0]
        del peer.requestqueue[0]
    if peer.passedturn:
        act = Action(9)
        act.movesstart = len(gst.register)-len(peer.turnmoves)
        act.movesend = act.movesstart+len(peer.turnmoves)
        act.moves = peer.turnmoves
        peer.requestqueue.append(act)
    return act

def apply_data (gst, opt, peer, act):
    if act.protocol == 7:
        if len(gst.register) < act.registerlenght:
            newact = Action(8)
            newact.movesstart = len(gst.register)
            newact.movesend = newact.movesstart\
                +min(10, act.registerlenght-len(gst.register))
            peer.requestqueue += [newact]
    if act.protocol == 9:
        if act.movesstart == len(gst.register):
            # actuator
            actuate(gst, act.moves)
            gst.register += act.moves
    if act.protocol == 10:
        peer.passedturn = False
        del gst.moves[:]
            
def net_client_process (gst, opt, peer, acc):
    if peer.packettimer < acc:
        peer.packettimer = acc+opt.lag
        act = generate_request(gst, opt, peer)
        data = act_encode(act)
        peer.clientSock.sendto(data, peer.hostAddr)
    try:
        data, addr = peer.clientSock.recvfrom(256)
        recvact = act_decode(data)
        print("recvd: "+str(recvact))
        peer.hostAddr = addr
        apply_data(gst, opt, peer, recvact)
    except BlockingIOError: pass
    except: traceback.print_exc()

def net_host (gst, opt, peer):
    peer.hostSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer.hostSock.bind(("", 34555))
    peer.hostSock.setblocking(False)
    print("opened host")
    if len(gst.players) == 0:
        pl = Player()
        pl.color = hsv_to_rgb(peer.lobbycolorangle/math.pi*180)
        gst.players.append(pl)

def net_host_process (gst, opt, peer):
    try:
        data, addr = peer.hostSock.recvfrom(256)
        recvact = act_decode(data)
        print(addr, ("recvdata host: " +str(recvact)))
        if recvact.protocol == 0:
            newact = Action(1)
            newact.playerindex = len(gst.players)
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
            pl = Player()
            pl.color = recvact.color_r, recvact.color_g, recvact.color_b
            gst.players.append(pl)
        if recvact.protocol == 2:
            newact = Action(3)
            newact.playernum = len(gst.players)
            newact.starting = peer.start
            newact.mapseed = peer.mapseed
            newact.mapsize = peer.mapsize
            newact.mapindex = peer.mapindex
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
        if recvact.protocol == 4:
            newact = Action(5)
            newact.playerindex = recvact.playerindex
            newact.color_r = gst.players[recvact.playerindex].color[0]
            newact.color_g = gst.players[recvact.playerindex].color[1]
            newact.color_b = gst.players[recvact.playerindex].color[2]
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
        if recvact.protocol == 6:
            newact = Action(7)
            newact.registerlenght = len(gst.register)
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
        if recvact.protocol == 8:
            newact = Action(9)
            newact.movesstart = recvact.movesstart
            newact.movesend = recvact.movesend
            newact.moves += gst.register[newact.movesstart:newact.movesend]
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
        if recvact.protocol == 9:
            if recvact.movesstart == len(gst.register):
                actuate(gst, recvact.moves)
                gst.register += recvact.moves
            newact = Action(10)
            newdata = act_encode(newact)
            peer.hostSock.sendto(newdata, addr)
    except BlockingIOError: pass
    except:
        traceback.print_exc()
        peer.hostSock.close(); peer.hostSock = None

def net_find (peer):
    print("opened client")
    peer.clientSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer.clientSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    peer.clientSock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    peer.clientSock.setblocking(False)
    act = Action(0)
    color = hsv_to_rgb(peer.lobbycolorangle/math.pi*180)
    act.color_r = color[0]
    act.color_g = color[1]
    act.color_b = color[2]
    data = act_encode(act)
    peer.clientSock.sendto(data, ('255.255.255.255', 34555))
    print("sent data "+str(data))

def generate_lobby_request (peer, gst):    
    act = Action(2)
    if len(peer.requestqueue) > 0:
        act = peer.requestqueue[0]
        del peer.requestqueue[0]
    return act

def apply_lobby_data (peer, gst, act):
    if act.protocol == 1:
        peer.id = act.playerindex
    if act.protocol == 3:
        peer.playernum = act.playernum
        peer.mapseed = act.mapseed
        peer.mapsize = act.mapsize
        peer.mapindex = peer.mapindex
        for i in range(peer.playernum):
            newact = Action(4)
            newact.playerindex = i
            peer.requestqueue += [newact]
        if act.starting == 1:
            peer.start = 1
    if act.protocol == 5:
        if act.playerindex >= len(gst.players):
            while act.playerindex > len(gst.players):
                gst.players.append(Player())
            pl = Player()
            pl.color = act.color_r, act.color_g, act.color_b
            gst.players.append(pl)
        else:
            color = act.color_r, act.color_g, act.color_b
            gst.players[act.playerindex].color = copy.copy(color)
            
def net_lobby_process (peer, opt, gst, acc):
    if peer.hostAddr != None:
        if peer.packettimer < acc:
            peer.packettimer = acc+200
            act = generate_lobby_request(peer, gst)
            data = act_encode(act)
            peer.clientSock.sendto(data, peer.hostAddr)
    try:
        data, addr = peer.clientSock.recvfrom(256)
        recvact = act_decode(data)
        print("recvd: "+str(recvact))
        peer.hostAddr = addr
        apply_lobby_data(peer, gst, recvact)
    except BlockingIOError: pass
    except:
        traceback.print_exc()
        peer.clientSock.close(); peer.clientSock = None

def process_lobby (scr, com, gst, loaded, opt, acc, peer):
    if peer.hostSock != None:
        net_host_process(gst, opt, peer)
    if peer.clientSock != None:
        net_lobby_process(peer, opt, gst, acc)

    if peer.start == 1:
        peer.requestqueue = list()
        refresh_colors(loaded, gst)
        refresh_zoom(loaded, gst)
        random.seed(peer.mapseed)
        create_map(gst, peer.mapsize, [opt.res[0]/2, opt.res[1]/2])
        return False
    
    tx, ty = opt.res[0]/2-300, opt.res[1]/2-225
    bx, by = opt.res[0]/2+300, opt.res[1]/2+225
    xm, ym = com.mousepos
    if com.mouse[0] == 1:
        if xm>tx+5 and xm<tx+300 and ym>ty+5 and ym<ty+25:
            if opt.gamemode == 0:
                peer.localplayers = copy.deepcopy(gst.players)
                gst.players = copy.deepcopy(peer.hostplayers)
                opt.gamemode = 1
            elif opt.gamemode == 1 and False:
                peer.hostplayers = copy.deepcopy(gst.players)
                gst.players = copy.deepcopy(peer.localplayers)
                opt.gamemode = 0

        if opt.gamemode == 0:
            if xm>tx+100 and xm<tx+130 and ym>ty+75 and ym<ty+95:
                pl = Player()
                pl.color = hsv_to_rgb(random.randint(1, 359))
                gst.players.append(pl)
            for i in range(len(gst.players)):
                if xm>tx+12 and ym>ty+106+i*25 \
                   and xm<tx+12+8 and ym<ty+106+i*25+8:
                    del gst.players[i]; break
            if xm>tx+280 and xm<tx+295 and ym>ty+50 and ym<ty+70:
                if pygame.key.get_mods() & pygame.KMOD_LSHIFT:
                    peer.mapsize = get_next_mapsize(peer.mapsize)
                else: peer.mapsize += 1
            if xm>tx+305 and xm<tx+320 and ym>ty+50 and ym<ty+70:
                if pygame.key.get_mods() & pygame.KMOD_LSHIFT:
                    peer.mapsize = get_prev_mapsize(peer.mapsize)
                else: peer.mapsize -= 1
            if xm>tx+(bx-tx)/2-50 and xm<tx+(bx-tx)/2+50 \
               and ym>by-25 and ym<by:
                # start local game
                refresh_colors(loaded, gst)
                refresh_zoom(loaded, gst)
                create_map(gst, peer.mapsize, [opt.res[0]/2, opt.res[1]/2])
                return False
        if opt.gamemode == 1:
            if peer.hostSock == None and peer.clientSock == None:
                if xm>tx+10 and xm<tx+100 and ym>ty+30 and ym<ty+50:
                    # host game
                    net_host(gst, opt, peer)
                if xm>tx+10 and xm<tx+100 and ym>ty+50 and ym<ty+70:
                    # find host
                    net_find(peer)
                if xm>tx+280 and xm<tx+295 and ym>ty+50 and ym<ty+70:
                    if pygame.key.get_mods() & pygame.KMOD_LSHIFT:
                        peer.mapsize = get_next_mapsize(peer.mapsize)
                    else: peer.mapsize += 1
                if xm>tx+305 and xm<tx+320 and ym>ty+50 and ym<ty+70:
                    if pygame.key.get_mods() & pygame.KMOD_LSHIFT:
                        peer.mapsize = get_prev_mapsize(peer.mapsize)
                    else: peer.mapsize -= 1
            if xm>tx+(bx-tx)/2-50 and xm<tx+(bx-tx)/2+50 \
               and ym>by-25 and ym<by and peer.hostSock != None:
                # start multiplayer game
                peer.start = 1
                
    if com.mouse[0] > 1 and opt.gamemode != 1:
        dx = (bx-30)-xm; dy = (ty+30)-ym
        if dx*dx+dy*dy < 30*30:
            peer.lobbycolorangle = math.atan2(dy, dx)+math.pi
            color = hsv_to_rgb(peer.lobbycolorangle/math.pi*180)
            peer.lobbycolor = color
            gst.players[0].color = color
            
    return True
    
def render_lobby (scr, com, gst, loaded, opt, acc, peer):
    tx, ty = opt.res[0]/2-300, opt.res[1]/2-225
    bx, by = opt.res[0]/2+300, opt.res[1]/2+225

    # BACKGROUND
    if ty > 40:
        title = loaded.fonttitle.render("SLAY", 4,(255, 255, 255))
        scr.blit(title, (tx+(bx-tx)/2-title.get_width()/2, ty-50))
    if tx > 0:
        color = hsv_to_rgb(peer.lobbycolorangle/math.pi*180)
        for i in range(0, int(tx/6)):
            x = tx%6+i*6
            a = math.sin(acc*0.001+i)*min(i*i*0.2, 150)
            p = x, a+opt.res[1]/2; q = x, -a+opt.res[1]/2
            col = [color[c]*(i/int(tx/6)) for c in range(3)]
            pygame.draw.line(scr, col, p, q)
        for j in range(0, int(tx/6)):
            i = int(tx/6)-j
            x = tx%6-i*6+opt.res[0]
            a = math.sin(acc*0.001+i)*min(i*i*0.2, 150)
            p = x, a+opt.res[1]/2; q = x, -a+opt.res[1]/2
            col = [color[c]*(i/int(tx/6)) for c in range(3)]
            pygame.draw.line(scr, col, p, q)
        
    
    pygame.draw.rect(scr, (255, 255, 255), (tx, ty, bx-tx, by-ty), 0)
    pygame.draw.rect(scr, (100, 100, 100), (tx, ty, bx-tx, by-ty), 1)

    scr.blit(loaded.imgs[24], (bx-370, by-400))

    color = hsv_to_rgb(peer.lobbycolorangle/math.pi*180)
    pygame.gfxdraw.filled_circle(scr, int(bx-30), int(ty+30), 20, color)
    pygame.gfxdraw.aacircle(scr, int(bx-30), int(ty+30), 20, (0, 0, 0))
    pos = [bx-30, ty+30]
    pos[0] += math.cos(peer.lobbycolorangle)*19.5
    pos[1] += math.sin(peer.lobbycolorangle)*19.5
    pygame.gfxdraw.line(scr, int(bx-30), int(ty+30),
        int(pos[0]), int(pos[1]), (0,0,0))

    scr.blit(loaded.font.render("GAMEMODE:", 4,(0,0,0)), (tx+10, ty+5))
    if opt.gamemode == 0:
        scr.blit(loaded.font.render(
            "LOCAL", 4,(0,0,0)), (tx+120, ty+5))
    if opt.gamemode == 1:
        scr.blit(loaded.font.render(
            "ONLINE (multiplayer only)", 4,(0,0,0)), (tx+120, ty+5))

    if opt.gamemode == 1:
        if peer.hostSock == None and peer.clientSock == None:
            scr.blit(loaded.font.render(
                "HOST", 4,(0,0,0)), (tx+10, ty+30))
            scr.blit(loaded.font.render(
                "FIND", 4,(0,0,0)), (tx+10, ty+50))
            scr.blit(loaded.font.render(
                "[+]", 4,(0,0,0)), (tx+280, ty+50))
            scr.blit(loaded.font.render(
                "[-]", 4,(0,0,0)), (tx+305, ty+50))
        txt = "RANDOM MAP (SEED= "+str(peer.mapseed)+")"
        scr.blit(loaded.font.render(
            txt, 4,(0,0,0)), (tx+200, ty+30))
        scr.blit(loaded.font.render(
            "MAP SIZE", 4,(0,0,0)), (tx+200, ty+50))
        col = (30,130,0) if calc_good_mapsize(peer.mapsize) else (0,0,0)
        scr.blit(loaded.font.render(
            str(peer.mapsize), 4,col), (tx+330, ty+50))

    if opt.gamemode == 0:
        scr.blit(loaded.font.render(
            "PLAYERS", 4,(0,0,0)), (tx+10, ty+75))
        scr.blit(loaded.font.render(
            "ADD", 4,(0,0,0)), (tx+100, ty+75))
        scr.blit(loaded.font.render(
            "[+]", 4,(0,0,0)), (tx+280, ty+50))
        scr.blit(loaded.font.render(
            "[-]", 4,(0,0,0)), (tx+305, ty+50))
        scr.blit(loaded.font.render(
            "MAP SIZE", 4,(0,0,0)), (tx+200, ty+50))
        col = (30,130,0) if calc_good_mapsize(peer.mapsize) else (0,0,0)
        scr.blit(loaded.font.render(
            str(peer.mapsize), 4,col), (tx+330, ty+50))
        
    for i in range(0, len(gst.players)):
        if i == peer.id:
            scr.blit(loaded.font.render(
                "YOU", 4,(0,0,0)), (tx+52, ty+98+i*25))
        elif gst.players[i].mind == 0:
            scr.blit(loaded.font.render(
                "HUMAN", 4,(0,0,0)), (tx+52, ty+98+i*25))
            
        pygame.draw.rect(scr, gst.players[i].color,
            (tx+25, ty+100+i*25, 20, 20))
        pygame.draw.rect(scr, (0,0,0),
            (tx+25, ty+100+i*25, 20, 20), 1)

        pygame.draw.rect(scr, (200,200,200),
            (tx+12, ty+106+i*25, 8, 8))
        pygame.draw.line(scr, (40,40,40),
            (tx+12+2, ty+106+i*25+2), (tx+12+5, ty+106+i*25+5))
        pygame.draw.line(scr, (40,40,40),
            (tx+12+5, ty+106+i*25+2), (tx+12+2, ty+106+i*25+5))
        pygame.draw.rect(scr, (0,0,0),
            (tx+12, ty+106+i*25, 8, 8), 1)
    
    scr.blit(loaded.font.render("START", 4,(0,0,0)), (tx+(bx-tx)/2, by-25))
    
    pygame.display.flip()
    scr.fill((30, 30, 30))

def main():
    opt = Opt() #
    
    pygame.init()
    displayflags = pygame.HWACCEL|pygame.DOUBLEBUF|pygame.RESIZABLE
    scr = pygame.display.set_mode(opt.res, displayflags)

    com = Commands() #
    loaded = Loaded() #
    gst = Gamestate() #
    peer = LocalPeer() #

    pl = Player(); pl.color = [255, 0, 0]; gst.players.append(pl)
    pl = Player(); pl.color = [255, 255, 0]; gst.players.append(pl)
    pl = Player(); pl.color = [255, 150, 0]; gst.players.append(pl)
    pl = Player(); pl.color = [0, 255, 0]; gst.players.append(pl)
    pl = Player(); pl.color = [255, 0, 255]; gst.players.append(pl)

    load(loaded)
    peer.lobbycolorangle = random.random()*(math.pi*2)
    peer.mapseed = random.randint(0, 1024*1024*1024)
    peer.mapsize = 1+6+12+18+24+30+36+42

    clock = pygame.time.Clock()
    acc = 0; lobby = True
    run = True
    while run:
        tick = clock.tick(60)
        acc += tick

        run = com.update()
        if opt.res != com.res:
            opt.res = com.res
            scr = pygame.display.set_mode(opt.res, displayflags)
        if lobby:
            lobby = process_lobby(scr, com, gst, loaded, opt, acc, peer)
            render_lobby(scr, com, gst, loaded, opt, acc, peer)
        else:
            process(scr, com, gst, loaded, opt, acc, peer)
            render(scr, com, gst, loaded, opt, acc, peer)

    pygame.quit()

try: main()
except: pygame.quit(); traceback.print_exc(); input()
