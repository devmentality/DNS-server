import struct
import socket
import asyncio
import random
from dns_structs import (DNSPackage, Question,
     construct_query_from_questions,
     construct_response_from_answers,
     get_parent_domain)
from package_decode import decode_package
from common import types, classes
from caching import Cache, CsvCacheManager
from async_socket import AsyncSocket


def log_rrs(rrs):
    for rr in rrs:
        print(rr.__dict__)

ADDR = '127.0.0.1'
PORT = 53
ROOT = '198.41.0.4'

class AsyncServer:
    def __init__(self, loop, cache):
        self.server_sock = None
        self.loop = loop
        self.cache = cache

    async def run(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sock.bind((ADDR, PORT))
        self.server_sock.setblocking(False)
        self.server_sock = AsyncSocket(self.loop, self.server_sock)

        print('DNS server listening on {0}:{1}'.format(ADDR, PORT))

        while True:
            client_task = self.server_sock.recvfrom(1024)
            # required for proper signal propagation on Windows
            timeout_task = asyncio.sleep(2) 
            done, pending = await asyncio.wait(
                [client_task, timeout_task], 
                return_when=asyncio.FIRST_COMPLETED)
            
            if client_task in done:
                byte_query, client_addr = client_task.result()
                self.loop.create_task(self.serve_client(byte_query, client_addr))
            else:
                client_task.cancel()

    async def serve_client(self, byte_query, client_addr):
        print('Query from {0}:{1}'.format(*client_addr))
        parsed_query = decode_package(byte_query)

        await self.process_query(parsed_query, client_addr)

    async def process_query(self, query, client_addr):
        tasks = [
            self.process_question(question)
            for question in query.questions
        ]

        done, pending = await asyncio.wait(tasks)
        # smth like get results of all tasks and compose response
        print('successfully resolved')
        answers_to_send = []
        for task in done:
            answers_to_send += task.result()

        dns_response = construct_response_from_answers(query.id, answers_to_send)
        self.server_sock.sendto(dns_response.to_bytes(), client_addr) 

    async def process_question(self, question):
        print('Question is {}'.format(question.__dict__))
        cached_answers = self.cache.find_answers(question)

        if len(cached_answers) > 0:
            print('resolved from cache')
            return cached_answers

        ns_addr = self.find_nearest_ns(question.name)
        answers = await self.get_answers_from_ns(ns_addr, question)
        return answers

    def find_nearest_ns(self, domain_name):
        domain = get_parent_domain(domain_name)

        while domain != '':
            ns_q = Question(domain, types['NS'], 1)
            auth_ns = self.cache.find_answers(ns_q)
            if len(auth_ns) > 0:
                for ans in auth_ns:
                    addr_q = Question(ans.data, types['A'], 1)

                    answers = self.cache.find_answers(addr_q)
                    if len(answers) > 0:
                        return answers[0].data
            domain = get_parent_domain(domain)

        print('use root')
        return ROOT 

    async def get_answers_from_ns(self, ns_addr, question):
        # returns tuple: answers, authorities, additions
        print('Question to ns is {}'.format(question.__dict__))
        response = None

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock_to_ns:
            sock_to_ns.setblocking(False)
            sock_to_ns = AsyncSocket(self.loop, sock_to_ns)
            #query_id = random.randrange(1, 2**16)
            query_id = 1

            query_to_ns = construct_query_from_questions(
                query_id, [question])
            sock_to_ns.sendto(query_to_ns.to_bytes(), (ns_addr, PORT))
            response = await self.try_receive_response(sock_to_ns, question, query_id)

        if response is None:
            return []

        print('Got from ns {}'.format(ns_addr))
        answers, authorities, additions = self.process_response(response)

        if len(answers) != 0: 
            # ns answered
            return answers
        
        if len(authorities) > 0:
            # there are some authorities to ask
            next_ns_name = authorities[0].data
            print('delegation to')
            next_ns_ip = await self.resolve_ns_name(next_ns_name)
            return await self.get_answers_from_ns(next_ns_ip, question)
        
        return []

    async def resolve_ns_name(self, ns_name):
        question = Question(ns_name, types['A'], 1)
        print('start resolving authority')
        answers = await self.process_question(question)
        a_answers = [
            answer for answer in answers if answer.name == ns_name and answer.tp == types['A']
            ]
        if len(a_answers) > 0:
            return a_answers[0].data
        return None


    def process_response(self, response):
        print('{0} answers'.format(len(response.answers)))
        log_rrs(response.answers)
        print('{0} authorities'.format(len(response.authorities)))
        log_rrs(response.authorities)
        print('{0} additions'.format(len(response.additions)))
        log_rrs(response.additions)

        answers = list(self.filter_supported_records(response.answers))
        authorities = list(self.filter_supported_records(response.authorities))
        additions = list(self.filter_supported_records(response.additions))

        records_to_cache = answers + authorities + additions

        for record in records_to_cache:
            self.cache.add_answer(record)

        return answers, authorities, additions

    async def try_receive_response(self, sock_to_ns, question, query_id, attempts=10):
        attempts = 10
        while attempts > 0:
            byte_response, source_ip = await sock_to_ns.recvfrom(1024)
            response = decode_package(byte_response)
            if response.id == query_id:
                return response
            attempts -= 1
        return None

    def filter_supported_records(self, records):
        for record in records:
            if record.tp in types.values():
                yield record
