import argparse
import uvicorn

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Plataforma individual local Indexing Methods')
    parser.add_argument('--port',type=int,default=18766)
    args=parser.parse_args()
    uvicorn.run('workbench.api:app',host='127.0.0.1',port=args.port,workers=1)
