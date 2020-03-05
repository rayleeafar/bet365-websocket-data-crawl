import socket
import asyncio
import websockets
from websockets.extensions import permessage_deflate
import time
import logging
import argparse
import threading
import requests
import sys
import collections  

logger = logging.getLogger(__name__)

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class WSClient():

    _MAP_LEN = 64
    _charMap = [
        ["A", "d"], ["B", "e"], ["C", "f"], ["D", "g"], ["E", "h"], ["F", "i"], ["G", "j"], 
        ["H", "k"], ["I", "l"], ["J", "m"], ["K", "n"], ["L", "o"], ["M", "p"], ["N", "q"], ["O", "r"], 
        ["P", "s"], ["Q", "t"], ["R", "u"], ["S", "v"], ["T", "w"], ["U", "x"], ["V", "y"], ["W", "z"], 
        ["X", "a"], ["Y", "b"], ["Z", "c"], ["a", "Q"], ["b", "R"], ["c", "S"], ["d", "T"], ["e", "U"], 
        ["f", "V"], ["g", "W"], ["h", "X"], ["i", "Y"], ["j", "Z"], ["k", "A"], ["l", "B"], ["m", "C"], 
        ["n", "D"], ["o", "E"], ["p", "F"], ["q", "0"], ["r", "1"], ["s", "2"], ["t", "3"], ["u", "4"], 
        ["v", "5"], ["w", "6"], ["x", "7"], ["y", "8"], ["z", "9"], ["0", "G"], ["1", "H"], ["2", "I"], 
        ["3", "J"], ["4", "K"], ["5", "L"], ["6", "M"], ["7", "N"], ["8", "O"], ["9", "P"], 
        ["\n", ":|~"], ["\r", ""]
    ]
               
    _WSS_URLS_CONNECTION = 'wss://premws-pt1.365lpodds.com/zap/'
    _URLS_SESSION_ID = 'https://www.bet365.com.cy/defaultapi/sports-configuration'
    _URLS_NSTTOKEN_ID = 'https://www.bet365.com.cy/'
    
    _REQ_EXTENSIONS = [permessage_deflate.ClientPerMessageDeflateFactory(
                server_max_window_bits=15,
                client_max_window_bits=15,
                compress_settings={'memLevel': 4},
            )]
    _REQ_PROTOCOLS = ['zap-protocol-v1']

    R_HEADER = collections.namedtuple('Header','name value')
    _REQ_HEADERS = [
            R_HEADER('Sec-WebSocket-Version', '13'),
            R_HEADER('Accept-Encoding', 'gzip, deflate, br'),
            R_HEADER('Pragma', 'no-cache'),
            R_HEADER('User-Agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.122 Safari/537.36')
    ]

    def __init__(self, url=None, **kwargs):
        self.url = url or self._WSS_URLS_CONNECTION
        # set some default values
        self.reply_timeout = kwargs.get('reply_timeout') or 60
        self.sleep_time = kwargs.get('sleep_time') or 5
        self.callback = kwargs.get('callback')


    async def listen_forever(self):
        while True:
        # outer loop restarted every time the connection fails
            logger.debug('Creating new connection...')
            sessio_id = self._fetch_session_id()
            nst_token = self._fetch_nst_token()
            nst_auth_token = self._gen_nst_auth_code_str(nst_token)
            try:
                async with websockets.connect(self.url,extra_headers=self._REQ_HEADERS,
                                        extensions=self._REQ_EXTENSIONS,subprotocols=self._REQ_PROTOCOLS) as ws:
                    
                    message = f'\x23\x03P\x01__time,S_{sessio_id},D_{nst_auth_token}\x00'
                    await ws.send(message)
                    logger.debug(f"> {message}")

                    while True:
                    # listener loop
                        try:
                            reply = await asyncio.wait_for(ws.recv(), timeout=self.reply_timeout)
                        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                            logger.debug(
                                f'Websocket(timeout or closed) error - retrying connection in {self.sleep_time} sec (Ctrl-C to quit)')
                            await asyncio.sleep(self.sleep_time)
                            break
                        logger.debug(f'Server said > {reply}')
                        if self.callback:
                            await self.callback(reply,ws)
            except socket.gaierror:
                logger.debug(
                    f'Socket error - retrying connection in {self.sleep_time} sec (Ctrl-C to quit)')
                await asyncio.sleep(self.sleep_time)
                continue
            except ConnectionRefusedError:
                logger.debug('Nobody seems to listen to this endpoint. Please check the URL.')
                logger.debug(f'Retrying connection in {self.sleep_time} sec (Ctrl-C to quit)')
                await asyncio.sleep(self.sleep_time)
                continue

    def _fetch_session_id(self):
        # return "C177352B35422FC2802D329E7FCEBF84000003"
        headers = {
            'Host': 'www.bet365.com',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0',
            'Upgrade-Insecure-Requests': '1',
            'Cookie': 'aps03=ct=212&lng=2',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Referer': 'https://www.bet365.com/'
        }
        logger.debug('fetching session id...')
        response = None
        try:
            response = requests.get(self._URLS_SESSION_ID, headers=headers)
        except Exception:
            pass
        if not response:
            logger.debug('session id: N/A')
            return
        session_id = response.cookies['pstk']
        logger.debug(f'session id:{session_id}')
        return session_id

    def _fetch_nst_token(self):
        # return "+MXWaW==.paO54cialSmSmiOiWc4YJVdUEhfDRgomrmlTQ4VbQOK="
        # d[b('0x0')] = 'paO54cialSmSmiOiWc4YJVdUEhfDRgomrmlTQ4VbQOK='
        # d[b('0x1')] = '+MXWaW=='

        headers = {
            'Host': 'www.bet365.com',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0',
            'Upgrade-Insecure-Requests': '1',
            'Cookie': 'aps03=ct=212&lng=2',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Referer': 'https://www.bet365.com/'
        }
        logger.debug('fetching nst token ...')
        response = None
        try:
            response = requests.get(self._URLS_NSTTOKEN_ID, headers=headers)
        except Exception:
            pass
        if not response:
            logger.debug('nst token id: N/A')
            return
        import re
        
        # pattern1 = re.compile("var[\s]+order[\s]*=[\s]*\[\\\'.*?\\\'\];")
        # pattern2 = re.compile("var[\s]+loadingflags[\s]*=[\s]*\[\\\'.*?\\\'\];")
        pattern1 = re.compile("d\[b\(\\'0x1\\\'\)\][\s]*=[\s]*\\\'.*?\\\'[\s]*;")
        pattern2 = re.compile("d\[b\(\\'0x0\\\'\)\][\s]*=[\s]*\\\'.*?\\\'[\s]*;")
        r1= pattern1.findall(response.text)
        r2= pattern2.findall(response.text)
        if len(r1) > 0 and len(r2) > 0:
            sr1 = r1[0].split('\'')[3]
            sr2 = r2[0].split('\'')[3]
            nst_token = '.'.join([sr1,sr2])
            logger.debug(f'nst token id:{nst_token}')
            return nst_token
        return

    def _gen_nst_auth_code_str(self,nst_token):
        # session_id = self._fetch_session_id()
        # nst_token = self._fetch_nst_token()
        D_str = self._nst_decrypt(nst_token)
        logger.debug(f"nst auth str:{D_str}")
        return D_str

    def _nst_encrypt(self,nst_token):
        
        ret = ""
        for r in range(len(nst_token)):
            n = nst_token[r]
            for s in range(self._MAP_LEN):
                if n == self._charMap[s][0]:
                    n = self._charMap[s][1]
                    break
            ret += n
        return ret

    def _nst_decrypt(self,nst_token):    

        ret = ""
        nst_token_len = len(nst_token)
        r= 0
        while nst_token_len>r:
            n = nst_token[r]
            for s in range(self._MAP_LEN):
                if ":" == n and ":|~" == nst_token[r, r+3]:
                    n = "\n"
                    r += 2
                    break
                if (n == self._charMap[s][1]) :
                    n = self._charMap[s][0]
                    break
            ret += n
            r +=1
        return ret
   


def start_ws_client(client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.listen_forever())


async def callback_fn(data,ws,*args, **kwargs):
    # Write here your logic
    if data.startswith('100'):
        req = str('\x16\x00CONFIG_1_3,OVInPlay_1_3,Media_L1_Z3,XL_L1_Z3_C1_W3\x01')
        await ws.send(req)
        return
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--url',
                        required=False,
                        # set here your URL
                        default=None,
                        dest='url',
                        help='Websocket URL')

    parser.add_argument('--reply-timeout',
                        required=False,
                        dest='reply_timeout',
                        type=int,
                        help='Timeout for reply from server')

    parser.add_argument('--sleep',
                        required=False,
                        type=int,
                        dest='sleep_time',
                        default=None,
                        help='Sleep time before retrieving connection')

    args = parser.parse_args()

    ws_client = WSClient(**vars(args), callback=callback_fn)
    start_ws_client(ws_client)
