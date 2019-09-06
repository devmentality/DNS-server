'''
        [query_ID, from_addr] - key for queries

        (query_ID, from_addr) -> answers from cache
        to_forwarder_ID -> (query_ID, from_addr)

        def serve client:
            get recevied query
            parse query
            answers, questions to lookup = call(try get from cache)
           

        def try get from cache:
            ...

        def query server:
            create client socket
            set socket nonblocking
            query forwarder  
            add client socket to selector with callback = finish_query    

    
        def finish query:
            !!! you have to know ID
            having to forwarder socket, clinet addr, already got answers:
            receive pkg from forwarder
            parse answers
            construct response to client
            send response via server socket
    '''