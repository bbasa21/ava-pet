# AVA PET - Snake & Ladder
# ESP32-authoritative game client.

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget

SNAKES={99:54,95:75,92:88,89:68,74:53,64:36,62:19,49:11,47:26,16:6}
LADDERS={2:38,7:14,8:31,15:26,21:42,28:84,36:44,51:67,71:91,78:98}

class DiceWidget(Widget):
    value=NumericProperty(0)
    def __init__(self,**kwargs):
        super().__init__(**kwargs); self.bind(pos=self._draw,size=self._draw,value=self._draw); Clock.schedule_once(lambda *_:self._draw(),0)
    def _draw(self,*_):
        self.canvas.clear()
        with self.canvas:
            Color(.12,.07,.20,1); RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(12)]); Color(1,1,1,1)
            pad=min(self.width,self.height)*.14; RoundedRectangle(pos=(self.x+pad,self.y+pad),size=(self.width-2*pad,self.height-2*pad),radius=[dp(7)])
            if self.value in range(1,7): self._dots(int(self.value))
    def _dots(self,v):
        l=self.x+self.width*.30; r=self.x+self.width*.70; m=self.x+self.width*.50; b=self.y+self.height*.30; t=self.y+self.height*.70; c=self.y+self.height*.50; rad=min(self.width,self.height)*.055
        p={1:[(m,c)],2:[(l,t),(r,b)],3:[(l,t),(m,c),(r,b)],4:[(l,t),(r,t),(l,b),(r,b)],5:[(l,t),(r,t),(m,c),(l,b),(r,b)],6:[(l,t),(r,t),(l,c),(r,c),(l,b),(r,b)]}
        for x,y in p[v]: Color(.12,.07,.20,1); Ellipse(pos=(x-rad,y-rad),size=(rad*2,rad*2))
    def set_value(self,v): self.value=int(v)

class SnakeLadderBoard(Widget):
    player_ali=NumericProperty(0); player_ava=NumericProperty(0)
    def __init__(self,font_name='Roboto',**kwargs):
        self.font_name=font_name; super().__init__(**kwargs); self.number_labels=[]
        self.ali_label=Label(text='A',font_name=font_name,bold=True,color=(1,1,1,1),size_hint=(None,None)); self.ava_label=Label(text='V',font_name=font_name,bold=True,color=(1,1,1,1),size_hint=(None,None)); self.add_widget(self.ali_label); self.add_widget(self.ava_label)
        for n in range(1,101):
            lab=Label(text=str(n),font_name=font_name,font_size=dp(7.5),color=(1,1,1,.82),size_hint=(None,None),halign='center',valign='middle'); lab.bind(size=lambda o,*_:setattr(o,'text_size',o.size)); self.number_labels.append(lab); self.add_widget(lab)
        self.bind(pos=self._redraw,size=self._redraw); Clock.schedule_once(lambda *_:self._redraw(),0)
    def square_center(self,s):
        s=max(1,min(100,int(s))); i=s-1; row=i//10; col=i%10
        if row%2: col=9-col
        cw=self.width/10.; ch=self.height/10.; return self.x+(col+.5)*cw,self.y+(row+.5)*ch
    def square_position(self,s):
        s=max(1,min(100,int(s))); i=s-1; row=i//10; col=i%10
        if row%2: col=9-col
        cw=self.width/10.; ch=self.height/10.; return self.x+col*cw,self.y+row*ch,cw,ch
    def _redraw(self,*_):
        self.canvas.clear()
        with self.canvas:
            Color(.035,.025,.065,1); RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(14)]); cw=self.width/10.; ch=self.height/10.
            for s in range(1,101):
                px,py,_,_=self.square_position(s); Color(.16,.09,.23,1) if (s+(s-1)//10)%2==0 else Color(.09,.055,.15,1); Rectangle(pos=(px+dp(.8),py+dp(.8)),size=(max(0,cw-dp(1.6)),max(0,ch-dp(1.6)))); Color(1,1,1,.16); Line(rectangle=(px,py,cw,ch),width=.6)
            for a,b in LADDERS.items(): self._draw_ladder(a,b)
            for a,b in SNAKES.items(): self._draw_snake(a,b)
            self._draw_token(self.player_ali,.20,.65,1.0); self._draw_token(self.player_ava,1,.25,.70)
        for s,lab in enumerate(self.number_labels,1):
            px,py,cw,ch=self.square_position(s); lab.pos=(px+dp(2),py+dp(1)); lab.size=(cw-dp(4),ch-dp(2))
        self._position_token_label(self.ali_label,self.player_ali,-.13); self._position_token_label(self.ava_label,self.player_ava,.13)
    def _position_token_label(self,lab,s,off):
        if not s: lab.opacity=0; return
        cx,cy=self.square_center(s); size=max(dp(13),min(self.width,self.height)/18.); lab.opacity=1; lab.size=(size,size); lab.center=(cx+self.width/10.*off,cy); lab.font_size=max(dp(7),size*.48)
    def _draw_ladder(self,a,b):
        x1,y1=self.square_center(a); x2,y2=self.square_center(b); dx,dy=x2-x1,y2-y1; ln=max(1.,(dx*dx+dy*dy)**.5); nx,ny=-dy/ln,dx/ln; off=max(dp(3.5),min(self.width,self.height)*.018); Color(.95,.76,.16,1); Line(points=[x1+nx*off,y1+ny*off,x2+nx*off,y2+ny*off],width=dp(2)); Line(points=[x1-nx*off,y1-ny*off,x2-nx*off,y2-ny*off],width=dp(2))
        for i in range(1,7):
            t=i/7.; cx,cy=x1+dx*t,y1+dy*t; Line(points=[cx+nx*off,cy+ny*off,cx-nx*off,cy-ny*off],width=dp(1.25))
    def _draw_snake(self,a,b):
        x1,y1=self.square_center(a); x2,y2=self.square_center(b); dx,dy=x2-x1,y2-y1; ln=max(1.,(dx*dx+dy*dy)**.5); nx,ny=-dy/ln,dx/ln; amp=max(dp(3.5),min(self.width,self.height)*.02); pts=[]
        for i in range(21):
            t=i/20.; w=amp*(1 if i%2 else -1); pts.extend([x1+dx*t+nx*w,y1+dy*t+ny*w])
        Color(.92,.18,.52,1); Line(points=pts,width=dp(3),joint='round'); Color(1,.35,.58,1); Ellipse(pos=(x1-dp(5),y1-dp(5)),size=(dp(10),dp(10))); Color(.03,.02,.05,1); Ellipse(pos=(x1-dp(2.7),y1+dp(.8)),size=(dp(1.8),dp(1.8))); Ellipse(pos=(x1+dp(.9),y1+dp(.8)),size=(dp(1.8),dp(1.8)))
    def _draw_token(self,s,r,g,b):
        if not s:return
        cx,cy=self.square_center(s); rad=max(dp(7),min(self.width,self.height)/36.); Color(.02,.02,.03,.65); Ellipse(pos=(cx-rad-dp(1),cy-rad-dp(1)),size=(rad*2+dp(2),rad*2+dp(2))); Color(r,g,b,1); Ellipse(pos=(cx-rad,cy-rad),size=(rad*2,rad*2)); Color(1,1,1,.9); Line(circle=(cx,cy,rad),width=dp(1))
    def set_positions(self,a,v): self.player_ali=int(a); self.player_ava=int(v)

class SnakeLadderGame:
    def __init__(self,board,status_label=None,dice_widget=None,turn_label=None):
        self.board=board; self.status_label=status_label; self.dice_widget=dice_widget; self.turn_label=turn_label; self.app=App.get_running_app(); self.ali=0; self.ava=0; self.turn='ALI'; self.finished=False; self.rolling=False; self.remote_started=False; self.roll_token=object(); self._install_ble_hook(); self.reset(local_only=True); Clock.schedule_once(lambda *_:self._start_remote(),.2); Clock.schedule_interval(self._watch_connection,.25)
    def _install_ble_hook(self):
        if self.app is None or getattr(self.app,'_snake_hook',False): return
        original=self.app.handle_game_data; game=self
        def wrapped(text):
            value=str(text).strip()
            if value.upper().startswith('SNAKE_'): game.handle_ble_message(value); return
            original(value)
        self.app.handle_game_data=wrapped; self.app._snake_hook=True
    def _ble_ready(self):
        try:return bool(self.app and self.app.ble.connected and self.app.ble.ready)
        except Exception:return False
    def _start_remote(self):
        if self._ble_ready() and self.app.ble.write_data('SNAKE_START'): self.remote_started=True
    def _watch_connection(self,*_):
        if not self.app:return
        page=getattr(self.app,'snake_page',None)
        if page is not None and not self._ble_ready() and self.remote_started and page.opacity>0:
            page.opacity=0; page.disabled=True; finding=getattr(self.app,'finding_page',None)
            if finding is not None:finding.opacity=1; finding.disabled=False
            label=getattr(self.app,'finding_label',None)
            if label is not None:label.text='Finding AVA'
            self.remote_started=False
    def _hide_snake_page(self,*_):
        page=getattr(self.app,'snake_page',None) if self.app else None
        if page is not None: page.opacity=0; page.disabled=True
    def reset(self,local_only=False):
        self.ali=0; self.ava=0; self.turn='ALI'; self.finished=False; self.rolling=False; self.roll_token=object(); self.board.set_positions(0,0)
        if self.dice_widget:self.dice_widget.set_value(0)
        if self.turn_label:self.turn_label.text="ALI'S TURN"
        if self.status_label:self.status_label.text='ROLL THE DICE'
        if self.app and not getattr(self.app,'_snake_back_hook',False):
            page=getattr(self.app,'snake_page',None)
            if page is not None:
                for child in list(page.children):
                    if isinstance(child,Button) and str(child.text).strip().upper()=='BACK': child.bind(on_release=self._hide_snake_page); break
                self.app._snake_back_hook=True
        if not local_only and self._ble_ready(): self.app.ble.write_data('SNAKE_RESET'); Clock.schedule_once(lambda *_:self._start_remote(),.15)
    def roll(self):
        if self.finished or self.rolling or self.turn!='ALI':return
        if not self._ble_ready():
            if self.status_label:self.status_label.text='AVA NOT READY'
            return
        self.rolling=True; self.roll_token=object(); token=self.roll_token; frames=[1,2,3,4,5,6,5,4,3,2]
        if self.status_label:self.status_label.text='ALI ROLLING...'
        def frame(i):
            if token is not self.roll_token or self.finished:return
            if self.dice_widget:self.dice_widget.set_value(frames[i])
            if i+1<len(frames):Clock.schedule_once(lambda *_:frame(i+1),.07)
        frame(0)
        if not self.app.ble.write_data('SNAKE_ROLL'):
            self.rolling=False
            if self.status_label:self.status_label.text='ROLL SEND FAILED'
    def _apply_position(self,p,pos):
        if p=='ALI':self.ali=int(pos)
        elif p=='AVA':self.ava=int(pos)
        else:return
        self.board.set_positions(self.ali,self.ava)
    def handle_ble_message(self,text):
        parts=str(text).strip().split('|'); msg=parts[0].upper() if parts else ''
        try:
            if msg=='SNAKE_STARTED': self.remote_started=True; self.reset(local_only=True); return
            if msg=='SNAKE_RESET': self.reset(local_only=True); return
            if msg=='SNAKE_DICE' and len(parts)>=3:
                p=parts[1].upper(); v=int(parts[2])
                if 1<=v<=6:
                    if self.dice_widget:self.dice_widget.set_value(v)
                    self.rolling=False
                    if self.status_label:self.status_label.text=f'{p} ROLLED {v}'
                    if self.app:self.app.add_log(f'SNAKE DICE <- PLAYER={p} | DICE={v}')
                return
            if msg=='SNAKE_POSITION' and len(parts)>=4:
                p=parts[1].upper(); old=int(parts[2]); new=int(parts[3]); self._apply_position(p,new)
                if self.app:self.app.add_log(f'SNAKE POSITION <- PLAYER={p} | {old}->{new}')
                return
            if msg=='SNAKE_MOVE' and len(parts)>=5:
                p=parts[1].upper(); old=int(parts[2]); new=int(parts[3]); kind=parts[4].upper(); self._apply_position(p,new)
                if self.status_label:self.status_label.text=f'{p}: NEED EXACT ROLL' if new==old else (f'{p} CLIMBS TO {new}' if kind=='LADDER' else (f'{p} SLIDES TO {new}' if kind=='SNAKE' else f'{p} MOVES TO {new}'))
                return
            if msg=='SNAKE_TURN' and len(parts)>=2:
                self.turn=parts[1].upper()
                if self.turn not in ('ALI','AVA'):return
                if self.turn_label:self.turn_label.text=f"{self.turn}'S TURN"
                if self.turn=='AVA':self._start_ava_visual_roll()
                else:
                    self.rolling=False
                    if self.status_label:self.status_label.text='ROLL THE DICE'
                return
            if msg=='SNAKE_FINISHED':
                winner=parts[1].upper() if len(parts)>=2 else 'UNKNOWN'; self.finished=True; self.rolling=False
                if self.status_label:self.status_label.text=f'{winner} WINS!'
                if self.app:self.app.add_log(f'SNAKE FINISHED <- {winner}')
        except Exception as exc:
            if self.app:self.app.add_log(f'SNAKE DATA PARSE ERROR: {exc} | {text}')
    def _start_ava_visual_roll(self):
        self.rolling=True; self.roll_token=object(); token=self.roll_token; frames=[6,2,5,1,4,3,2,6,4,5]
        if self.status_label:self.status_label.text='AVA ROLLING...'
        def frame(i):
            if token is not self.roll_token or self.finished:return
            if self.dice_widget:self.dice_widget.set_value(frames[i])
            if i+1<len(frames):Clock.schedule_once(lambda *_:frame(i+1),.07)
        frame(0)

def build_snake_ladder_page(font_name,back_callback,roll_callback,reset_callback):
    from kivy.uix.floatlayout import FloatLayout
    page=FloatLayout(size_hint=(1,1))
    page.add_widget(Label(text='SNAKE & LADDER',font_name=font_name,font_size=dp(22),color=(1,1,1,1),size_hint=(1,None),height=dp(42),pos_hint={'center_x':.5,'top':.98}))
    turn=Label(text="ALI'S TURN",font_name=font_name,font_size=dp(12),color=(1,1,1,.92),size_hint=(1,None),height=dp(28),pos_hint={'center_x':.5,'top':.91}); page.add_widget(turn)
    ali=Label(text='ALI  0',font_name=font_name,font_size=dp(9),color=(.25,.75,1,1),size_hint=(.30,None),height=dp(26),pos_hint={'x':.05,'top':.91}); ava=Label(text='AVA  0',font_name=font_name,font_size=dp(9),color=(1,.35,.72,1),size_hint=(.30,None),height=dp(26),pos_hint={'right':.95,'top':.91}); page.add_widget(ali); page.add_widget(ava)
    board=SnakeLadderBoard(font_name=font_name,size_hint=(.92,None),height=dp(360),pos_hint={'center_x':.5,'top':.84}); page.add_widget(board)
    dice=DiceWidget(size_hint=(None,None),size=(dp(64),dp(64)),pos_hint={'center_x':.82,'y':.095}); page.add_widget(dice)
    status=Label(text='ROLL THE DICE',font_name=font_name,font_size=dp(9.5),color=(1,1,1,.95),size_hint=(.52,None),height=dp(46),pos_hint={'x':.05,'y':.105},halign='left',valign='middle'); status.bind(size=lambda o,*_:setattr(o,'text_size',o.size)); page.add_widget(status)
    def hud(*_):ali.text=f'ALI  {board.player_ali}'; ava.text=f'AVA  {board.player_ava}'
    board.bind(player_ali=hud,player_ava=hud)
    rb=Button(text='ROLL DICE',font_name=font_name,font_size=dp(11),size_hint=(None,None),size=(dp(122),dp(42)),pos_hint={'center_x':.25,'y':.025},background_normal='',background_down='',background_color=(.45,.12,.75,.95),color=(1,1,1,1)); rb.bind(on_release=lambda *_:roll_callback()); page.add_widget(rb)
    xb=Button(text='RESET',font_name=font_name,font_size=dp(10),size_hint=(None,None),size=(dp(82),dp(38)),pos_hint={'center_x':.52,'y':.027},background_normal='',background_down='',background_color=(.25,.08,.42,.95),color=(1,1,1,1)); xb.bind(on_release=lambda *_:reset_callback()); page.add_widget(xb)
    bb=Button(text='BACK',font_name=font_name,font_size=dp(10),size_hint=(None,None),size=(dp(76),dp(38)),pos_hint={'center_x':.78,'y':.027},background_normal='',background_down='',background_color=(.13,.13,.17,.95),color=(1,1,1,1)); bb.bind(on_release=lambda *_:back_callback()); page.add_widget(bb)
    return page,board,status,dice,turn,rb
