#! /usr/bin/env python

import socket
import struct
import threading
import Queue
import StringIO
import cv2
from PIL import Image
import protocol
import json
from time import sleep
import pdb
import sys
import select
import numpy as np
from config import Config

class ClientCommand(object):
    """ A command to the client thread.
        Each command type has its associated data:

        CONNECT:    (host, port) tuple
        SEND:       Data string
        RECEIVE:    None
        CLOSE:      None
    """
    CONNECT, SEND, RECEIVE, CLOSE = range(4)

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class ClientReply(object):
    """ A reply from the client thread.
        Each reply type has its associated data:

        ERROR:      The error string
        SUCCESS:    Depends on the command - for RECEIVE it's the received
                    data string, for others None.
    """
    ERROR, SUCCESS = range(2)

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class SocketClientThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """
    def __init__(self, cmd_q=None, reply_q=None):
        super(SocketClientThread, self).__init__()
        self.cmd_q = cmd_q or Queue.Queue()
        self.reply_q = reply_q or Queue.Queue()
        self.alive = threading.Event()
        self.alive.set() 
        self.socket = None

        self.handlers = {
            ClientCommand.CONNECT: self._handle_CONNECT,
            ClientCommand.CLOSE: self._handle_CLOSE,
            ClientCommand.SEND: self._handle_SEND,
            ClientCommand.RECEIVE: self._handle_RECEIVE,
        }

    def run(self):
        while self.alive.isSet():
            try:
                # Queue.get with timeout to allow checking self.alive
                cmd = self.cmd_q.get(True, 0.1)
                self.handlers[cmd.type](cmd)
            except Queue.Empty as e:
                continue

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)
        print '{} exit'.format(self.__class__.__name__)

    def _handle_CONNECT(self, cmd):
        try:
            print 'connect called\n'
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((cmd.data[0], cmd.data[1]))
            self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_CLOSE(self, cmd):
        self.socket.close()
        reply = ClientReply(ClientReply.SUCCESS)
        self.reply_q.put(reply)

    def _handle_SEND(self, cmd):
#        header = struct.pack('<L', len(cmd.data))
#        print 'sending data. length {}'.format(len(cmd.data))
        try:
            data_size = struct.pack("!I", len(cmd.data))
            self.socket.send(data_size)
            self.socket.sendall(cmd.data)
            self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    # def _handle_SEND_IMAGE(self, cmd):
    #     try:
    #         packet = struct.pack("!I%ds" % len(cmd.data),
    #                              len(cmd.data), cmd.data)
    #         self.socket.sendall(packet)
    #         self.reply_q.put(self._success_reply())
    #     except IOError as e:
    #         self.reply_q.put(self._error_reply(str(e)))

    def _handle_RECEIVE(self, cmd):
        try:
            header_data = self._recv_n_bytes(4)
            if len(header_data) == 4:
                msg_len = struct.unpack('<L', header_data)[0]
                data = self._recv_n_bytes(msg_len)
                if len(data) == msg_len:
                    self.reply_q.put(self._success_reply(data))
                    return
            self.reply_q.put(self._error_reply('Socket closed prematurely'))
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _recv_n_bytes(self, n):
        """ Convenience method for receiving exactly n bytes from
            self.socket (assuming it's open and connected).
        """
        data = ''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if chunk == '':
                break
            data += chunk
        return data

    def _error_reply(self, errstr):
        return ClientReply(ClientReply.ERROR, errstr)

    def _success_reply(self, data=None):
        return ClientReply(ClientReply.SUCCESS, data)



class ResultReceivingThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """
    
    def __init__(self, server_ip, port, reply_q=None):
        super(ResultReceivingThread, self).__init__()
        self.server_ip = server_ip
        self.port = port
        self.reply_q = reply_q or Queue.Queue()
        self.alive = threading.Event()
        self.alive.set() 
        self.socket = None

    def run(self):
        self.connect(self.server_ip, self.port)
        while self.alive.isSet():
            # listen for result
            if self.socket:
                input=[self.socket]
                inputready,outputready,exceptready = select.select(input,[],[]) 
                for s in inputready: 
                    if s == self.socket: 
                        # handle the server socket
                        data = self._handle_input_data()
                        self.reply_q.put(ClientReply(ClientReply.SUCCESS, data))
        self.socket.close()

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)
        print '{} exit'.format(self.__class__.__name__)
        
    def connect(self, ip, port):
        try:
            print 'connecting to result receviing port {}:{}\n'.format(ip, port)
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, port))
            print 'connect successfully to {}:{}\n'.format(ip, port)            
        except IOError as e:
            print 'connect failed\n'            
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_CLOSE(self, cmd):
        self.socket.close()
        reply = ClientReply(ClientReply.SUCCESS)
        self.reply_q.put(reply)

    def _handle_input_data(self):
        data_size = struct.unpack("!I", self._recv_all(4))[0]
        data = self._recv_all(data_size)
        return data
        
    def _recv_all(self, recv_size):
        '''
        Received data till a specified size.
        '''
        data = ''
        while len(data) < recv_size:
            tmp_data = self.socket.recv(recv_size - len(data))
            if tmp_data is None:
                print "Cannot recv data at %s" % str(self)
            if len(tmp_data) == 0:
                print "received 0 bytes"
                break
            data += tmp_data
        return data
        
    def _error_reply(self, errstr):
        return ClientReply(ClientReply.ERROR, errstr)

    def _success_reply(self, data=None):
        return ClientReply(ClientReply.SUCCESS, data)
        

def enlarge_roi(roi, padding, frame_width, frame_height):
    (x1, y1, x2, y2) = roi
    x1=max(x1-padding,0)
    y1=max(y1-padding,0)
    x2=min(x2+padding,frame_width-1)
    y2=min(y2+padding,frame_height-1)
    return (x1, y1, x2, y2)
        
# a gabriel client for new gabriel servers
# there is no token conrol mechanism
def run():
    video_capture = cv2.VideoCapture(0)
    cmd_q = Queue.Queue()
    network_thread=SocketClientThread(cmd_q=cmd_q)
    network_thread.start()
    cmd_q.put(ClientCommand(ClientCommand.CONNECT, (Config.GABRIEL_IP, Config.VIDEO_STREAM_PORT)) )

    reply_q=Queue.Queue()
    result_receiving_thread = ResultReceivingThread(Config.GABRIEL_IP, Config.RESULT_RECEIVING_PORT, reply_q=reply_q)
    result_receiving_thread.start()

    token_cnt=0
    try:
        id=0
        alive=True
        blur_rois=[]        
        while alive:
            # Capture frame-by-frame
            ret, frame = video_capture.read()
            ret, jpeg_frame=cv2.imencode('.jpg', frame)
            header={protocol.Protocol_client.JSON_KEY_FRAME_ID : str(id)}
            header_json=json.dumps(header)
            # this is designed for the new gabriel framework
            cmd_q.put(ClientCommand(ClientCommand.SEND, header_json))
            cmd_q.put(ClientCommand(ClientCommand.SEND, jpeg_frame.tostring()))

            try:
                resp=reply_q.get(timeout=0.01)
                height, width, _ = frame.shape
                padding=10
                if resp.type == ClientReply.SUCCESS:
                    blur_rois=[]
                    data=resp.data
                    data_json = json.loads(data)
                    result_data=json.loads(data_json['result'])
                    face_data=json.loads(result_data['value'])
                    num_faces=face_data['num']
                    for idx in range(0,num_faces):
                        face_roi = json.loads(face_data[str(idx)])
                        x1 = face_roi['roi_x1']
                        y1 = face_roi['roi_y1']
                        x2 = face_roi['roi_x2']
                        y2 = face_roi['roi_y2']
                        name = face_roi['name']
                        (x1, y1, x2, y2) = enlarge_roi( (x1,y1,x2,y2), padding, width, height)
                        blur_rois.append( (x1, y1, x2, y2) )
            except Queue.Empty:
                print 'no repsonse received'

            for roi in blur_rois:
                (x1, y1, x2, y2)=roi
                frame[y1:y2+1, x1:x2+1]=np.resize(np.array([0]), (y2+1-y1, x2+1-x1,3))
                cv2.rectangle(frame, (x1,y1), (x2, y2), (255,0,0), 5)

#            cv2.imshow('frame', frame)
            sleep(0.1)
            id+=1
    except KeyboardInterrupt:
        network_thread.join()
        result_receiving_thread.join()
        video_capture.release()
        print 'main program exit!'
