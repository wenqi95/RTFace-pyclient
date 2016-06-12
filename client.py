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
#from ui import set_image

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
                        self.reply_q.put(self._success_reply(data))
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

# not a thread safe class
class tokenManager(object):
    def __init__(self, token_num):
        super(self.__class__, self).__init__()        
        self.token_num=token_num
        # token val is [0..token_num)
        self.token_val=token_num -1
        self.lock = threading.Lock()

    def inc(self):
        self.token_val= (self.token_val + 1) if (self.token_val<self.token_num) else (self.token_val)

    def dec(self):
        self.token_val= (self.token_val - 1) if (self.token_val>=0) else (self.token_val)

    def empty(self):
        return (self.token_val<0)

    
train=False
training_name=None
cmd_q = Queue.Queue()
adding_person=False
whitelist=[]
people_to_remove=[]
def stop_train():
    global train
    global training_name
    train=False
    ret=training_name
    training_name=None
    return ret

def start_train(new_training_name):
    global train
    global training_name
    global adding_person
    training_name=new_training_name
    adding_person=True
    train=True
    
def reconnect():
    print 'reconnecting'
    cmd_q.put(ClientCommand(ClientCommand.CLOSE, (Config.GABRIEL_IP, Config.VIDEO_STREAM_PORT)))
    cmd_q.put(ClientCommand(ClientCommand.CONNECT, (Config.GABRIEL_IP, Config.VIDEO_STREAM_PORT)))

# check if rect1 and rect2 intersect
def intersect_rect(rect1, rect2):
    (r1_x1, r1_y1, r1_x2, r1_y2) = rect1
    (r2_x1, r2_y1, r2_x2, r2_y2) = rect2
    return not(r2_x1 > r1_x2
               or r2_x2 < r1_x1
               or r2_y1 > r1_y2
               or r2_y2 < r1_y1)

# check if a roi intersect with any of white list rois    
def overlap_whitelist_roi(whitelist_rois, roi):
    for whitelist_roi in whitelist_rois:
        # if intersect
        if intersect_rect(whitelist_roi, roi):
            return True
    return False

# a gabriel client for new gabriel servers
# there is no token conrol mechanism
def run(sig_frame_available, sig_server_info_available):
    global train
    global training_name
    global adding_person
    global whitelist
    global people_to_remove
    alive=True    
    tokenm = tokenManager(Config.TOKEN)
    video_capture = cv2.VideoCapture(0)
    network_thread=SocketClientThread(cmd_q=cmd_q)
    network_thread.start()
    cmd_q.put(ClientCommand(ClientCommand.CONNECT, (Config.GABRIEL_IP, Config.VIDEO_STREAM_PORT)) )

    reply_q=Queue.Queue()
    result_receiving_thread = ResultReceivingThread(Config.GABRIEL_IP, Config.RESULT_RECEIVING_PORT, reply_q=reply_q)
    result_receiving_thread.start()

    initialized=False
    token_cnt=0
    try:
        id=0
        blur_rois=[]        
        while alive:
            # Capture frame-by-frame
            ret, frame = video_capture.read()
            ret, jpeg_frame=cv2.imencode('.jpg', frame)
            if not tokenm.empty():
                header={protocol.Protocol_client.JSON_KEY_FRAME_ID : str(id)}
                # retrieve server names first
                if not initialized:
                    header[protocol.AppDataProtocol.TYPE_get_person]=True
                # need to reconnect. to disable the detetion and recognition thread in the server
                if train:
                    header[protocol.Protocol_client.JSON_KEY_TRAIN]=training_name
                    # only add person once
                    if adding_person:
#                        print 'adding person {}'.format(training_name)
                        header[protocol.Protocol_client.JSON_KEY_ADD_PERSON]=training_name
                        adding_person=False

                if len(people_to_remove) > 0:
                    header[protocol.Protocol_client.JSON_KEY_RM_PERSON]=people_to_remove.pop(0)
                        
                header_json=json.dumps(header)
                cmd_q.put(ClientCommand(ClientCommand.SEND, header_json))
                cmd_q.put(ClientCommand(ClientCommand.SEND, jpeg_frame.tostring()))
                tokenm.dec()

            try:
                resp=reply_q.get(timeout=0.02)
                tokenm.inc()
                height, width, _ = frame.shape
                padding=5
                blur_rois=[]
                whitelist_rois=[]
#                print 'whitelist: {}'.format(whitelist)
                if resp.type == ClientReply.SUCCESS:
                    data=resp.data
                    data_json = json.loads(data)
                    result_data=json.loads(data_json['result'])
                    type=result_data['type']
                    if type == protocol.AppDataProtocol.TYPE_get_person:
                        print 'server info: {}'.format(result_data)
                        val=json.loads(result_data['value'])
                        print 'val: {}'.format(val)
                        name_list=val['people']
                        print 'client.py name_list: {}'.format(name_list)
                        sig_server_info_available.emit(name_list)                        
                        initialized=True
                        
                    if not (type == protocol.AppDataProtocol.TYPE_train or type == protocol.AppDataProtocol.TYPE_detect):
                        # ignore other type of responses for now
                        continue
                    face_data=json.loads(result_data['value'])
                    num_faces=face_data['num']
                    face_rois=[]
                    for idx in range(0,num_faces):
                        face_roi = json.loads(face_data[str(idx)])
                        x1 = face_roi['roi_x1']
                        y1 = face_roi['roi_y1']
                        x2 = face_roi['roi_x2']
                        y2 = face_roi['roi_y2']
                        name = face_roi['name']
                        if name in whitelist:
                            print 'received whitelist roi {}'.format(face_roi)
                            whitelist_rois.append((x1, y1, x2, y2))
                        else:
                            (x1, y1, x2, y2) = enlarge_roi( (x1,y1,x2,y2), padding, width, height)
                            face_rois.append( (x1, y1, x2, y2) )
                    
                    if type == 'detect':
                        blur_rois=face_rois
                    elif type == 'train':
                        for (x1,y1,x2,y2) in face_rois:
                            cv2.rectangle(frame, (x1,y1), (x2, y2), (0,0,255), 1)
                            cv2.putText(frame,
                                            'train',
                                        (x1,y1),
                                            0,
                                            1,
                                            (0,0,255));                            
                        pass
                    else:
                        print 'unknown result type {}'.format(type)
            except Queue.Empty:
                pass

            for roi in blur_rois:
#                pdb.set_trace()
                if not overlap_whitelist_roi(whitelist_rois, roi):
                    (x1, y1, x2, y2)=roi
                    frame[y1:y2+1, x1:x2+1]=np.resize(np.array([0]), (y2+1-y1, x2+1-x1,3))
#                cv2.rectangle(frame, (x1,y1), (x2, y2), (255,0,0), 5)

            rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            sig_frame_available.emit(rgb_frame)
#            cv2.imwrite('frame.jpg',frame)
#            cv2.imshow('frame', frame)
            sleep(0.01)
            id+=1
            
        network_thread.join()
        result_receiving_thread.join()
        video_capture.release()
        print 'client exit!'        
    except KeyboardInterrupt:
        network_thread.join()
        result_receiving_thread.join()
        video_capture.release()
        print 'client exit!'
