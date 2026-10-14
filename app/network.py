"""Explicit local/LAN/Tailscale listeners; never changes Tailscale itself."""
import ipaddress,json,os,shutil,socket,subprocess,threading
from pathlib import Path

LABELS={'local':'This computer only','lan':'Local network','tailscale':'Tailscale'}
def tailscale_addresses():
    exe=shutil.which('tailscale')
    if not exe:
        candidate=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Tailscale/tailscale.exe'
        if candidate.is_file():exe=str(candidate)
    if not exe:raise ValueError('Tailscale is not installed. Install and sign in to Tailscale, then select this mode again.')
    try:
        r=subprocess.run([exe,'status','--json'],capture_output=True,text=True,timeout=8,creationflags=0x08000000 if os.name=='nt' else 0)
        status=json.loads(r.stdout)
        if r.returncode or status.get('BackendState')!='Running' or not status.get('Self',{}).get('Online',False):raise ValueError('Tailscale is not connected. Open Tailscale and sign in or connect first.')
        ips=[x for x in status.get('TailscaleIPs',[]) if ipaddress.ip_address(x).version==4]
        if not ips:raise ValueError('Tailscale has no IPv4 address yet.')
        return ips
    except (subprocess.SubprocessError,json.JSONDecodeError,OSError) as e:raise ValueError('Unable to read Tailscale status. Open Tailscale, connect, and retry.') from e

def lan_addresses():
    candidates=set()
    try:candidates.update(x[4][0] for x in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
    except OSError:pass
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1',80));candidates.add(s.getsockname()[0])
    except OSError:pass
    networks=[ipaddress.ip_network(x) for x in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']]
    ips=sorted(x for x in candidates if any(ipaddress.ip_address(x) in n for n in networks))
    if not ips:raise ValueError('No home-network IPv4 address found. Connect Wi-Fi or Ethernet and retry.')
    return ips

class Listeners:
    def __init__(self,store,Server):self.store=store;self.Server=Server;self.servers={};self.threads={};self.mode='local';self.stop_callback=None;self.restart_command=None
    def switch(self,mode):
        if mode not in LABELS:raise ValueError('Unknown connection mode')
        addresses=['127.0.0.1']+(lan_addresses() if mode=='lan' else tailscale_addresses() if mode=='tailscale' else [])
        port=int(self.store.config.get('port',8765));added={}
        try:
            for host in addresses:
                if host in self.servers:continue
                server=self.Server((host,port),self.store)
                server.stop_callback=self.stop_callback or self.close
                server.restart_command=self.restart_command
                added[host]=server
        except OSError:
            for s in added.values():s.server_close()
            raise ValueError('PACE could not use port '+str(port)+'. Exit the older PACE instance and retry.')
        from server import atomic_json
        old=dict(self.store.config)
        self.store.config.update(connection_mode=mode,host='127.0.0.1')
        try:atomic_json(self.store.config_path,self.store.config)
        except Exception:
            self.store.config=old
            for s in added.values():s.server_close()
            raise
        for host,s in added.items():
            self.servers[host]=s;t=threading.Thread(target=s.serve_forever,daemon=True);self.threads[host]=t;t.start()
        for host in list(self.servers):
            if host not in addresses:self.servers[host].shutdown();self.servers[host].server_close();self.threads.pop(host).join();del self.servers[host]
        self.mode=mode
    def describe(self):
        port=self.store.config.get('port',8765)
        return LABELS[self.mode]+'\n\n'+'\n'.join('http://'+host+':'+str(port) for host in self.servers)+'\n\nLocal network: allow PACE through Windows Firewall on your private network if prompted.\nHDR is available only at localhost/127.0.0.1 on this PC.'
    def close(self):
        for s in self.servers.values():s.shutdown();s.server_close()
        for t in self.threads.values():t.join()
        self.servers.clear();self.threads.clear()
