import struct
from common import types


def encode_name(name):
    # ensure name to by fully qualified
    encoded_name = bytearray()
    labels = name.split('.')
    for label in labels:
        encoded_name.append(len(label))
        encoded_name += bytearray(label.encode('ascii'))

    return bytes(encoded_name)


def get_parent_domain(domain_name):
    return '.'.join(domain_name.split('.')[1:])


def construct_query_from_questions(id, questions):
    dns_query = DNSPackage()
    dns_query.id = id
    dns_query.qr = 0
    dns_query.rd = 1
    dns_query.qdcount = len(questions)
    dns_query.questions = questions
    return dns_query


def construct_response_from_answers(id, answers):
    dns_response = DNSPackage()
    dns_response.id = id
    dns_response.qr = 1
    dns_response.ancount = len(answers)
    dns_response.answers = answers
    return dns_response


class DNSPackage:
    def __init__(self):
        # header values
        self.id = 0 # 16b
        self.qr = 0 # 1b
        self.opcode = 0 # 4b
        self.auth = 0 # 1b
        self.trunc = 0 # 1b
        self.rd = 0 # 1b
        self.ra = 0 # 1b
        self.z = 0 # 3b
        self.rcode = 0 # 4b

        self.qdcount = 0
        self.ancount = 0
        self.nscount = 0
        self.arcount = 0

        self.questions = []
        self.answers = []
        self.authorities = []
        self.additions = []
     
    def to_bytes(self):
        flags = self._flags_to_bytes()
        b_header = struct.pack('!HHHHHH', 
            self.id, flags, self.qdcount, self.ancount,
            self.nscount, self.arcount)

        b_questions = self._rrecords_to_bytes(self.questions)
        b_answers = self._rrecords_to_bytes(self.answers)
        b_authorities = self._rrecords_to_bytes(self.authorities)
        b_additions = self._rrecords_to_bytes(self.additions)
        
        return b_header + b_questions + b_answers + b_authorities + b_additions

    def _flags_to_bytes(self):
        flags = self.qr << 15
        flags |= self.opcode << 11
        flags |= self.auth << 10
        flags |= self.trunc << 9
        flags |= self.rd << 8
        flags |= self.ra << 7
        flags |= self.rcode
        return flags

    def _rrecords_to_bytes(self, records):
        return b''.join([record.to_bytes() for record in records])

    def dump(self):
        print('HEADER: id {0}, qr {1}'.format(self.id, self.qr))
        print('HAS {} QUESTIONS'.format(self.qdcount))
        for quesiton in self.questions:
            print(quesiton.__dict__)

        print('HAS {} ANSWERS'.format(self.ancount))
        for answer in self.answers:
            print(answer.__dict__)

        print('HAS {} AUTHORITIES'.format(self.nscount))
        for authority in self.authorities:
            print(authority.__dict__)

        print('HAS {} ADDITIONS'.format(self.arcount))
        for addition in self.additions:
            print(addition.__dict__)


class Question:
    def __init__(self, name, tp, cl):
        self.name = name
        self.tp = tp
        self.cl = cl

    def to_bytes(self):
        return encode_name(self.name) + struct.pack('!HH', self.tp, self.cl)
        

class Answer:
    def __init__(self, name, tp, cl, ttl, data):
       self.name = name
       self.tp = tp
       self.cl = cl
       self.ttl = ttl
       self.data = data

    def to_bytes(self):
        prefix = encode_name(self.name) + \
            struct.pack('!HHI', self.tp, self.cl, self.ttl)
        if self.tp == types['A']:
            encoded_data = Answer._encode_a_data(self.data)
        elif self.tp == types['NS'] or self.tp == types['PTR']:
            encoded_data = Answer._encode_name_data(self.data)
        else:
            encoded_data = self.data.encode('cp1251')

        rdlen = len(encoded_data)
        return prefix + struct.pack('!H', rdlen) + encoded_data

    @staticmethod
    def _encode_a_data(ip):
        ip_bytes = [struct.pack('!B', int(ip_part)) for ip_part in ip.split('.')]
        return b''.join(ip_bytes)

    @staticmethod
    def _encode_name_data(domain_name):
        return encode_name(domain_name)
