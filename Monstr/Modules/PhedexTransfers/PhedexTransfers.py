

import Monstr.Core.Utils as Utils
import Monstr.Core.DB as DB
import Monstr.Core.BaseModule as BaseModule

from datetime import timedelta
import json

from Monstr.Core.DB import Column, BigInteger, Integer, String, Float, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func


class PhedexTransfers(BaseModule.BaseModule):
    name = 'PhedexTransfers'
    table_schemas = {'main': (Column('id', Integer, primary_key=True),
                              Column('instance', String(10)),
                              Column('to', String(40)),
                              Column('from', String(40)),
                              Column('done_files', Integer),
                              Column('done_bytes', BigInteger),
                              Column('try_files', Integer),
                              Column('try_bytes', BigInteger),
                              Column('expire_files', Integer),
                              Column('expire_bytes', BigInteger),
                              Column('fail_files', Integer),
                              Column('fail_bytes', BigInteger),
                              Column('quality', Float), #from String
                              Column('time', DateTime(True)))
                              #rate: done_bytes/binwidth(3600)
                    }

    config = {'site': 'T1_RU_JINR'}

    HOSTNAME = "http://cmsweb.cern.ch"
    REQUESTS = {"prod": {"from": "/phedex/datasvc/json/prod/TransferHistory?from=<site>&binwidth=3600",
                         "to": "/phedex/datasvc/json/prod/TransferHistory?to=<site>&binwidth=3600"},
                "debug": {"from": "/phedex/datasvc/json/debug/TransferHistory?from=<site>&binwidth=3600",
                         "to": "/phedex/datasvc/json/debug/TransferHistory?to=<site>&binwidth=3600"}}

    def __init__(self):
        super(PhedexTransfers, self).__init__()
        self.db_handler = DB.DBHandler()

    def PrepareRetrieve(self):
        # TODO: Introduce filling of absent hours
        last_row = self.db_handler.get_session().query(func.max(self.tables['main'].c.time).label("max_time_done")).one()

        if last_row[0]:
            horizon = last_row[0] - timedelta(hours=3)
            #errors = Retrieve(horizon)
            avaliable_errors = self.db_handler.get_session().query(self.tables['main']).filter(self.tables['main'].c.time_done > (horizon).date()).all()
        else:
            horizon = Utils.epoch_to_datetime(0)
            #errors = Retrieve()
            avaliable_errors = []
        return {'horizon': horizon,
                'avaliable_errors': avaliable_errors}

    def Retrieve(self, params):
        insert_list = []
        retrieve_time = Utils.get_UTC_now().replace(minute=0, second=0, microsecond=0)
        for instance in self.REQUESTS:
            for direction in self.REQUESTS[instance]:
                url = self.HOSTNAME+ self.REQUESTS[instance][direction].replace('<site>', self.config['site'])
                json_raw = Utils.get_page(url)
                json_obj = json.loads(json_raw)['phedex']['link']
                for link in json_obj:
                    details = link['transfer'][0]
                    transfer = {'instance': instance,
                                'from': link['from'],
                                'to': link['to'],
                                'time': retrieve_time,
                                'done_files': details['done_files'],
                                'done_bytes': details['done_bytes'],
                                'try_files': details['try_files'],
                                'try_bytes': details['try_bytes'],
                                'expire_files': details['expire_files'],
                                'expire_bytes': details['expire_bytes'],
                                'fail_files': details['fail_files'],
                                'fail_bytes': details['fail_bytes'],
                                'quality': float(details['quality'])
                                }
        return {'main': insert_list}


    #==========================================================================
    #                 Web
    #==========================================================================    

    def lastStatus(self, incoming_params):
        response = {}
        try:
            default_params = {'delta': 8}
            params = self._create_params(default_params, incoming_params)
            result = []
            max_time = self.db_handler.get_session().query(func.max(self.tables['main'].c.time_done).label("max_time")).one()
            if max_time[0]:
                max_time = max_time[0]
                query = self.tables['main'].select(self.tables['main'].c.time_done > max_time - timedelta(hours=params['delta']))
                cursor = query.execute()
                resultProxy = cursor.fetchall()
                for row in resultProxy:
                    result.append(dict(row.items()))
            response = {'data': result, 
                        'applied_params': params,
                        'success': True}
        except Exception as e:
            response = {'data': result, 
                        'incoming_params': incoming_params,
                        'default_params': [[key, default_params[key], type(default_params[key]) ] for key in default_params],
                        'success': False,
                        'error': type(e).__name__ + ': ' + e.message}

        return response

    rest_links = {}


def main():
    X = PhedexTransfers()
    #X.ExecuteCheck()
    
if __name__=='__main__':
    main()