"""
python3 client.py [server to send message]
"""

import asyncio
import argparse
import sys

server_ports = {
    "Riley": 12600, 
    "Jaquez": 12601,
    "Juzang": 12602,
    "Campbell": 12603,
    "Bernard": 12604
}

class Client:
    def __init__(self , port, ip='127.0.0.1', name='client', message_max_length=1e6):
        """
        127.0.0.1 is the localhost
        port could be any port
        """
        self.ip = ip
        self.port = port
        self.name = name
        self.message_max_length = int(message_max_length)

    async def tcp_echo_client(self, message):
        """
        on client side send the message for echo
        """
        reader, writer = await asyncio.open_connection(self.ip, self.port)
        print(f'{self.name} send: {message!r}')
        writer.write(message.encode())

        data = await reader.read(self.message_max_length)
        print(f'{self.name} received: {data.decode()}')

        print('close the socket')
        # The following lines closes the stream properly
        # If there is any warning, it's due to a bug o Python 3.8: https://bugs.python.org/issue38529
        # Please ignore it
        writer.close()

    def run_until_quit(self):
        # start the loop
        while True:
            # collect the message to send
            message = input("Please input the next message to send: ")
            if message in ['quit', 'exit', ':q', 'exit;', 'quit;', 'exit()', '(exit)']:
                break
            else:
                asyncio.run(self.tcp_echo_client(message))


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Client Argument Parser')
    parser.add_argument('server_name', type=str, help='server name to send input')
    args = parser.parse_args()
    if not args.server_name in server_ports: 
        print("Error: Invalid server name.")
        sys.exit() 
    client = Client(server_ports[args.server_name])  
    client.run_until_quit()