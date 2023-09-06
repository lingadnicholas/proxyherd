import aiohttp 
import asyncio 
import time 
import argparse 
import sys 
import logging 
import json 
# port nums: 12600-12604 

server_ports = {
    "Riley": 12600, 
    "Jaquez": 12601,
    "Juzang": 12602,
    "Campbell": 12603,
    "Bernard": 12604
}
server_connections = {
    "Riley":["Jaquez", "Juzang"], 
    "Jaquez":["Riley", "Bernard"],
    "Juzang":["Campbell", "Riley", "Bernard"],
    "Campbell":["Bernard", "Juzang"], 
    "Bernard":["Jaquez", "Juzang", "Campbell"]
} 
google_places_api_key = "AIzaSyA_Jk4JRNGgIAz-hB9to5EoRA84nBTPeJU"

class Server: 
    def __init__(self, name, ip='127.0.0.1'):
        self.name = name 
        self.port = server_ports[name] 
        self.ip = ip 
        self.message_max_length = int(1e6) 
        #self.client_cache is a dictionary
        #client_name: coordinates, client_time, time_diff
        self.client_cache = {} 
    

    async def handle_connection(self, reader, writer):
        #on server side
        data = await reader.read(self.message_max_length)
        message = data.decode()
        #sendback_message = message

        #process command 
        split_message = message.split() 
        command = split_message[0] 
        logging.info(f'Server {self.name} received message: {message}')
        sendback_message = ''
        if command == 'IAMAT' and self.valid_iamat(split_message):
            sendback_message = await self.process_iamat(split_message)
        elif command == 'WHATSAT' and self.valid_whatsat(split_message): 
            sendback_message = await self.process_whatsat(split_message)
        elif command == 'AT': # AT messages are produced by programmer... so I assume they are correctly formatted.
            sendback_message = await self.process_at(split_message, message) 
        else: 
            logging.info('Invalid command received:') 
            sendback_message = f'? {message}'

        writer.write(sendback_message.encode())
        await writer.drain()
        log_msg = f'Server {self.name} output message: {sendback_message}'
        logging.info(log_msg) 
        writer.close()

    def valid_iamat(self, split_message): 
        if len(split_message) != 4: 
            logging.info("Invalid length for IAMAT:")
            return False 
        #TODO: Check coordinates in ISO 6709?
        #TODO: Check time in POSIX time? 
        return True 

    async def process_iamat(self, split_message): 
        cur_time = time.time() 

        client_id = split_message[1] 
        client_location = split_message[2] 
        client_time = split_message[3] 

        time_diff = cur_time - float(client_time)
        time_str = "" 
        if time_diff > 0:
            time_str = '+' + str(time_diff) 
        else: 
            time_str = str(time_diff) 

        sendback_message = f'AT {self.name} {time_str} {client_id} {client_location} {client_time}'
        
        self.client_cache[client_id] = [client_location, client_time, time_str] # Put client in cache 
        # add this server's name onto it, saying it sent the message out already
        flood_message = f"AT {client_id} {client_location} {client_time} {time_str} {self.name}"
        await self.flood(flood_message) # Send client to all
        return sendback_message 

    async def flood(self, message): 
        for other_server in server_connections[self.name]: 
            other_port = server_ports[other_server] 
            try: 
                logging.info(f'Server {self.name} opening connection to server {other_server}')
                reader, writer = await asyncio.open_connection(self.ip, other_port)
                writer.write(message.encode())
                await writer.drain() 
                logging.info(f'Server {self.name} successfully wrote message "{message}" to {other_server}. Closing connection')
                writer.close()
                await writer.wait_closed() 
                logging.info(f'Connection to {other_server} closed.')
            except: 
                logging.info(f'Error {self.name} opening connection to server {other_server}')


    def valid_whatsat(self, split_message): 
        if len(split_message) != 4: 
            logging.info("Invalid length for WHATSAT command")
            return False 
        #Check valid radii
        radius = int(split_message[2])
        if radius <= 0 or radius > 50: 
            logging.info("Invalid radius")
            return False 
        upper_bound = int(split_message[3])
        if upper_bound <= 0 or upper_bound > 20: 
            logging.info("Invalid upper bound") 
            return False 
        
        #Check valid client
        if split_message[1] not in self.client_cache: 
            logging.info("Client not in cache")
            return False 
        return True 

    async def process_whatsat(self, split_message):
       #FOR TESTING PURPOSES. REMOVE. Just making sure client cache works
       #TEST (to Riley): IAMAT kiwi +34.068930-118.445127 1621464827.959498503
       #TEST (to all): WHATSAT kiwi 10 5 
       # should return +34.068930-118.445127
       #client_id = split_message[1]
       #message = f'AT {client_id}:{self.client_cache[client_id]}'
       #return message 
        client_id = split_message[1] 
        coordinates = self.client_cache[client_id][0] 
        client_time = self.client_cache[client_id][1] 
        time_diff = self.client_cache[client_id][2] 
        radius = str(int(split_message[2]) * 1000)
        upper_bound = int(split_message[3])
        
        # split coordinates 
        lat,lng = self.split_coordinates(coordinates)
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&key={google_places_api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                response = await resp.text()
                json_data = json.loads(response)
                results = json_data["results"]
                if len(results) > upper_bound: 
                    json_data["results"] = results[:upper_bound] 
                
                decoded_data = json.dumps(json_data, indent=4)
                decoded_data = str(decoded_data).replace('\n\n', '\n')
                decoded_data = decoded_data.rstrip('\n')
                message = f'AT {self.name} {time_diff} {client_id} {coordinates} {client_time}\n{decoded_data}\n\n'
                return message 

    def split_coordinates(self, coords):
        sign_pos=0
        for index, char in enumerate(coords[1:], 1): 
            if char == '+' or char == '-': 
                sign_pos = index 
                break 
        lat = coords[:sign_pos]
        lng = coords[sign_pos:]
        return (lat, lng)

    async def process_at(self, split_message, message): 
    # self.client_cache[client_id] = [client_location, client_time, time_str] # Put client in cache 
    # flood_message = f"AT {client_id} {client_location} {client_time} {time_str}"
        client_id = split_message[1] 
        client_location = split_message[2] 
        client_time = split_message[3] 
        time_str = split_message[4] 
        flooding_list = split_message[5:]
        send_msg = message 
        if self.name not in flooding_list: 
            send_msg = send_msg + f" {self.name}"
            logging.info(f'AT message "{message}" RECEIVED: Updated client cache, now flooding')
            self.client_cache[client_id] = [client_location, client_time, time_str]
            await self.flood(send_msg) 
        else: 
            if len(flooding_list) == 5: 
                logging.info(f"All servers have received the message: don't flood") 
            else: 
                logging.info(f"{self.name} did not change client cache: message indicated it was already updated, forwarding message")
                await self.flood(send_msg)
        return message 


    async def run_forever(self):
        server = await asyncio.start_server(self.handle_connection, self.ip, self.port)
        logging.info(f'Server {self.name} opened connection on port {self.port}')
        # Serve requests until Ctrl+C is pressed
        async with server:
            await server.serve_forever()
        # Close the server
        logging.info(f'Server {self.name} closed connection')
        server.close()
    

def main(): 
    parser = argparse.ArgumentParser(description = "Process server name")
    parser.add_argument('server_name', type=str, help='input is server name')
    args = parser.parse_args() 
    if args.server_name not in server_ports: 
        print("Error: Invalid server name.")
        sys.exit()
    server_name = args.server_name 
    server = Server(server_name)
    logging.basicConfig(filename=f"{server_name}.log", filemode='w', level=logging.INFO)
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__": 
    main()