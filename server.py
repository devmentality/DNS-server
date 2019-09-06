import struct
import socket
import selectors
from dns_structs import (DNSPackage, Question,
     construct_query_from_questions,
     construct_response_from_answers)
from package_decode import decode_package
from common import types, classes
from caching import Cache, CsvCacheManager


def log_rrs(rrs):
    for rr in rrs:
        print(rr.__dict__)

def get_parent_domain(domain_name):
    return '.'.join(domain_name.split('.')[1:])

class CallbackData:
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs


class QueryData:
    def __init__(self, questions, answers):
        self.remained_questions = set(questions)
        self.answers = answers


class Server:
    LOCALHOST = '127.0.0.1'
    PORT = 53
    ROOT = '198.41.0.4'

    def __init__(self, cache):
        self.server_sock = None
        self.selector = selectors.DefaultSelector()
        self.cache = cache
        # (addr, ID) -> answers
        self.cached_answers_by_query = dict()
        self.out_query_id_count = 0
        self.data_by_query = dict()

    def run(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sock.bind((Server.LOCALHOST, Server.PORT))
        self.server_sock.setblocking(False)
        print('DNS server listening on {0}:{1}'.format(Server.LOCALHOST, Server.PORT))
        self.selector.register(self.server_sock, selectors.EVENT_READ, 
            CallbackData(self._serve_client))
        
        while True:
            events = self.selector.select(timeout=2)
            for key, _ in events:
                payload = key.data
                payload.callback(*payload.args, **payload.kwargs)
    
    def _serve_client(self):
        byte_query, client_addr = self.server_sock.recvfrom(1024)
        print('Query from {0}:{1}'.format(*client_addr))
        parsed_query = decode_package(byte_query)
        self._process_query(client_addr, parsed_query)

    def _process_query(self, client_addr, query):
        self.data_by_query[(client_addr, query.id)] = QueryData(query.questions, [])
        for question in query.questions:
            self._process_question(client_addr, query.id, question)

    def _process_question(self, client_addr, query_id, question):
        print('Question is {}'.format(question.__dict__))
        answers = self.cache.find_answers(question)
        ns_address = self._find_nearest_ns(question.name)

        if len(answers) != 0:
            self._set_question_as_answered(client_addr, query_id, question, answers)
        else:
            self._query_ns(query_id, client_addr, ns_address, question)

    def _find_nearest_ns(self, question_name):
        domain = get_parent_domain(question_name)
        while domain != '':
            q = Question(domain, types['A'], 1)
            answers = self.cache.find_answers(q)
            if len(answers) > 0:
                return answers[0].data
            domain = get_parent_domain(domain)

        return Server.ROOT

    def _query_ns(self, client_query_id, client_addr, ns_address, question):
        sock_to_ns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_to_ns.setblocking(False)
        sock_to_ns.bind(('', 0))
        
        self.out_query_id_count += 1
        self.out_query_id_count %= 1 << 16
        query_to_ns = construct_query_from_questions(
            self.out_query_id_count, [question])
        print('Query ns {0} with ID = {1}'.format(ns_address, self.out_query_id_count))
        print('VIA socket {}'.format(sock_to_ns.getsockname())) 
        
        sock_to_ns.sendto(query_to_ns.to_bytes(), (ns_address, Server.PORT))
        self.selector.register(sock_to_ns, selectors.EVENT_READ, 
            CallbackData(
                self._process_answer_from_ns, sock_to_ns, 
                client_query_id, client_addr, question))

    def _process_answer_from_ns(self, sock_to_ns, client_query_id, client_addr, question):
        byte_response, _ = sock_to_ns.recvfrom(1024)
        parsed_response = decode_package(byte_response)
        answers = list(self._filter_supported_records(parsed_response.answers))
        authorities = list(self._filter_supported_records(parsed_response.authorities))
        additions = list(self._filter_supported_records(parsed_response.additions))

        print('Got {0} answers from forwarder'.format(len(parsed_response.answers)))
        log_rrs(parsed_response.answers)
        print('Got {0} authorities from forwarder'.format(len(parsed_response.authorities)))
        log_rrs(parsed_response.authorities)
        print('Got {0} additions from forwarder'.format(len(parsed_response.additions)))
        log_rrs(parsed_response.additions)

        records_to_cache = answers + authorities + additions
        for record in records_to_cache:
            self.cache.add_answer(record)

        self.selector.unregister(sock_to_ns)
        if len(answers) != 0: 
            # ns answered
            self._set_question_as_answered(client_addr, client_query_id, question, parsed_response.answers)
            print('Sucessful')
        elif len(additions) > 0:
            # ns delegates
            next_ns = additions[0].data
            self._query_ns(client_query_id, client_addr, next_ns, question)
            print('Delegation')
        else:
            self._set_question_as_answered(client_addr, client_query_id, question, parsed_response.answers)
            print('Unsuccessful')
            
    def _set_question_as_answered(self, client_addr, query_id, question, answers):
        quety_data = self.data_by_query[(client_addr, query_id)]
        quety_data.answers += answers
        quety_data.remained_questions.remove(question)

        if len(quety_data.remained_questions) == 0:
            self._respond_to_client(client_addr, query_id)

    def _filter_supported_records(self, records):
        for record in records:
            if record.tp in types.values():
                yield record
    
    def _respond_to_client(self, client_addr, query_id):
        answers = self.data_by_query[(client_addr, query_id)].answers
        dns_response = construct_response_from_answers(query_id, answers)
        self.server_sock.sendto(dns_response.to_bytes(), client_addr)
