import argparse
import asyncio
import json

from .common import ROOT, read_json


def main():
    parser=argparse.ArgumentParser(description='Local document retrieval experiments')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('fetch')
    index=commands.add_parser('index')
    index.add_argument('--corpus',choices=['adpf54','dom-casmurro','all'],default='all')
    index.add_argument('--refresh',action='store_true')
    extract=commands.add_parser('extract')
    extract.add_argument('--corpus',choices=['adpf54','dom-casmurro'],required=True)
    extract.add_argument('--variant',choices=list('ABCDEF'),default='F')
    extract.add_argument('--repetition',type=int,default=0)
    extract.add_argument('--fields',nargs='+')
    bench=commands.add_parser('benchmark')
    bench.add_argument('--name',default='full')
    bench.add_argument('--repetitions',type=int,default=3)
    bench.add_argument('--variants',default='ABCDEF')
    bench.add_argument('--fields',nargs='+')
    report=commands.add_parser('report')
    report.add_argument('--name',default='full')
    args=parser.parse_args()
    if args.command=='fetch':
        from .fetch import fetch_all
        fetch_all()
    elif args.command=='index':
        from .indexing import build_index
        corpora=['adpf54','dom-casmurro'] if args.corpus=='all' else [args.corpus]
        for corpus in corpora:
            print(json.dumps(build_index(corpus,args.refresh),ensure_ascii=False),flush=True)
    elif args.command=='extract':
        from .extraction import extract_form
        print(asyncio.run(extract_form(args.corpus,args.variant,args.repetition,args.fields)))
    elif args.command=='benchmark':
        from .benchmark import benchmark
        benchmark(args.repetitions,args.variants,args.name,args.fields)
    elif args.command=='report':
        from .report import render_report
        print(render_report(args.name))


if __name__=='__main__':
    main()
