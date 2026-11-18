"""Dollar-first, read-only broker reconciliation and recommendation linkage.

Broker exports contain no recommendation IDs. Contract/time links are
inferences, never promoted to confirmed intent or causal strategy alpha.
"""
from collections import Counter,defaultdict,deque
import csv
from dataclasses import asdict
from datetime import datetime,time
import hashlib
import json
from pathlib import Path
import re
from statistics import median
from zoneinfo import ZoneInfo
from broker_reconciliation import load_thinkorswim_trades,load_current_option_positions
from capital_ledger import parse_cash_ledger,parse_account_snapshot

ET=ZoneInfo('America/New_York')
FIELDS=['RecommendationID','RecommendationDate','ticker','option_strategy','expiration','strike',
    'contracts','allocation_decision','execution_entry_price','stop_loss_price','profit_target_price',
    'ResearchScore','portfolio_score','execution_score','broker_delta','implied_volatility',
    'PolicyEvidenceFingerprint','ProductionRiskPolicyVersion','OpeningHourPolicyVersion','SnapshotPath']


def num(value):
    try:return float(value)
    except (TypeError,ValueError):return None


def local(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return d.astimezone(ET).replace(tzinfo=None) if d.tzinfo else d


def key(row):
    return (row['ticker'].upper(),row['expiration'][:10],float(row['strike']),row['option_type'].upper())


def recommendations(path):
    """Bounded-field projection; retain duplicate-ID conflicts, not giant JSON."""
    csv.field_size_limit(20_000_000)
    ids={};conflicts=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        for raw in csv.DictReader(handle):
            rid=raw.get('RecommendationID')
            if not rid or raw.get('option_strategy') not in ('Long Call','Long Put'):continue
            row={f:raw.get(f,'') for f in FIELDS}
            try:
                row['at']=local(row['RecommendationDate'])
                row['key']=(row['ticker'].upper(),row['expiration'][:10],float(row['strike']),
                            'PUT' if row['option_strategy']=='Long Put' else 'CALL')
            except (ValueError,TypeError):continue
            if rid in ids and any(ids[rid][f]!=row[f] for f in FIELDS[:12]):conflicts.add(rid)
            else:ids.setdefault(rid,row)
    groups=defaultdict(list)
    for rid,row in ids.items():
        row['id_conflict']=rid in conflicts;groups[row['key']].append(row)
    return groups


def match_plan(contract,at,plans):
    prior=[r for r in plans.get(contract,[]) if r['at']<=at]
    allocated=[r for r in prior if r['allocation_decision'].lower()=='allocate']
    pool=allocated or prior
    if not pool:return {'link_status':'UNMATCHED','candidate_ids':[]}
    day=max(r['at'].date() for r in pool)
    choices=[r for r in pool if r['at'].date()==day]
    if len(choices)!=1 or any(r['id_conflict'] for r in choices):
        return {'link_status':'AMBIGUOUS_CONTRACT_TIME','candidate_ids':[r['RecommendationID'] for r in choices]}
    r=choices[0]
    status=('INFERRED_SAME_DAY_ALLOCATED' if day==at.date() else 'INFERRED_PRIOR_DAY_ALLOCATED') if allocated else 'MATCHING_RESEARCH_NOT_ALLOCATED'
    return {'link_status':status,'candidate_ids':[r['RecommendationID']],
        'recommendation_id':r['RecommendationID'],'recommendation_at':r['at'].isoformat(),
        'recommended_quantity':num(r['contracts']),'entry_limit':num(r['execution_entry_price']),
        'original_stop':num(r['stop_loss_price']),'original_target':num(r['profit_target_price']),
        'research_score':num(r['ResearchScore']),'portfolio_score':num(r['portfolio_score']),
        'execution_score':num(r['execution_score']),'broker_delta':num(r['broker_delta']),
        'implied_volatility':num(r['implied_volatility']),
        'core_policy_fingerprint':r['PolicyEvidenceFingerprint'],
        'production_risk_version':r['ProductionRiskPolicyVersion'],'opening_hour_version':r['OpeningHourPolicyVersion']}


def load_sources(directory,end):
    counts=Counter();cash={};manifest=[];errors=[]
    for path in sorted(Path(directory).glob('*AccountStatement*.csv')):
        if path.name[:10]>end:continue
        try:
            rows=Counter(load_thinkorswim_trades(path));counts|=rows
            for r in parse_cash_ledger(path):cash[r['EventID']]=r
            manifest.append({'source':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'fills':sum(rows.values())})
        except (ValueError,StopIteration,IndexError) as exc:
            errors.append({'source':path.name,'error_type':type(exc).__name__})
    trades=sorted(counts.elements(),key=lambda t:(t.executed_at,t.ticker,t.expiration,t.strike,t.side))
    return trades,list(cash.values()),manifest,errors


def reconstruct(initial,final,trades,cash,start,end,plans):
    inventory=defaultdict(deque);rows=[];used=Counter();fee_groups=defaultdict(float);quantities=Counter()
    selected=[t for t in trades if start<local(t.executed_at)<=end]
    for t in selected:quantities[(t.executed_at,t.ticker)]+=t.quantity
    for r in cash:
        if not start<local(r['ExecutedAt'])<=end or r['EventType']!='TRD':continue
        match=re.search(r'\b(?:BOT|SOLD)\s+[+-]?\d+\s+(\S+)\s+100\b',r['Description'])
        if match:fee_groups[(r['ExecutedAt'],match[1])]+=-float(r['MiscFees'])-float(r['CommissionsFees'])
    for p in initial:
        for i in range(abs(p['quantity'])):
            inventory[key(p)].append({'ticker':p['ticker'],'expiration':p['expiration'],'strike':p['strike'],
                'option_type':p['option_type'],'side':1 if p['quantity']>0 else -1,
                'entry':p['entry_price'],'period_basis':p['mark'],'entry_at':None,'entry_fee':0.,
                'unit_id':'INHERITED-'+str(key(p))+'-'+str(i),'link_status':'INHERITED_ORIGIN_UNRESOLVED',
                'economic_origin':'INHERITED_AT_BASELINE'})
    missing_fees=[]
    for fill_index,t in enumerate(selected):
        contract=t.contract_key;at=local(t.executed_at);direction=1 if t.side=='BUY' else -1
        fee_key=(t.executed_at,t.ticker)
        if fee_key not in fee_groups:missing_fees.append({'at':t.executed_at,'ticker':t.ticker})
        fee=fee_groups.get(fee_key,0.)/quantities[fee_key]
        plan=match_plan(contract,at,plans)
        for i in range(t.quantity):
            queue=inventory[contract]
            if queue and queue[0]['side']!=direction:
                lot=queue.popleft();gross=lot['side']*(t.price-lot['period_basis'])*100
                if lot.get('recommendation_id'):used[lot['recommendation_id']]-=1
                full_gross=lot['side']*(t.price-lot['entry'])*100
                rows.append({**lot,'status':'CLOSED','exit_at':t.executed_at,'exit':t.price,'exit_order_type':t.order_type,
                    'gross_period_contribution':gross,'gross_full_trade':full_gross,'fees':lot['entry_fee']+fee,
                    'net_period_contribution':gross-lot['entry_fee']-fee,
                    'exit_vs_original_stop':(t.price-lot['original_stop'])*100 if lot.get('original_stop') else None,
                    'exit_vs_original_target':(t.price-lot['original_target'])*100 if lot.get('original_target') else None,
                    'holding_hours':(at-local(lot['entry_at'])).total_seconds()/3600 if lot['entry_at'] else None})
            else:
                link=plan if direction==1 else {'link_status':'UNSUPPORTED_SHORT','candidate_ids':[]}
                rid=link.get('recommendation_id');qty=link.get('recommended_quantity')
                beyond=bool(rid and qty is not None and used[rid]>=qty)
                if rid:used[rid]+=1
                lot={'ticker':t.ticker,'expiration':t.expiration,'strike':t.strike,'option_type':t.option_type,
                    'side':direction,'entry':t.price,'period_basis':t.price,'entry_at':t.executed_at,'entry_fee':fee,
                    'unit_id':hashlib.sha256((str(t)+str(fill_index)+str(i)).encode()).hexdigest()[:24],**link,
                    'above_recorded_recommendation_quantity':beyond,
                    'economic_origin':'NEW_LONG' if direction==1 else 'NEW_SHORT',
                    'broker_open_effect':t.position_effect,
                    'entry_price_variance_vs_limit':(link['entry_limit']-t.price)*100 if direction==1 and link.get('entry_limit') else None}
                queue.append(lot)
    final_map={key(p):p for p in final}
    observed={k:sum(l['side'] for l in q) for k,q in inventory.items() if q}
    expected={key(p):p['quantity'] for p in final}
    if observed!=expected:raise ValueError('Ending exact contract inventory mismatch: '+str((observed,expected)))
    for k,queue in inventory.items():
        for lot in queue:
            p=final_map[k];gross=lot['side']*(p['mark']-lot['period_basis'])*100
            rows.append({**lot,'status':'OPEN','mark':p['mark'],'gross_period_contribution':gross,
                'gross_full_trade':lot['side']*(p['mark']-lot['entry'])*100,'fees':lot['entry_fee'],
                'net_period_contribution':gross-lot['entry_fee']})
    return rows,missing_fees


def build(directory,journal,beginning,ending):
    journal_hash=hashlib.sha256(Path(journal).read_bytes()).hexdigest()
    directory=Path(directory);start_path=directory/beginning;end_path=directory/ending
    a=parse_account_snapshot(start_path);b=parse_account_snapshot(end_path)
    start=datetime.combine(datetime.fromisoformat(a.as_of_date).date(),time(16))
    end=datetime.combine(datetime.fromisoformat(b.as_of_date).date(),time(16))
    if start>=end:raise ValueError('Ending statement must follow the beginning statement')
    if start.year!=end.year:raise ValueError('Cross-year YTD/fee bridge requires separate year-boundary accounting')
    trades,cash,manifest,errors=load_sources(directory,b.as_of_date)
    initial=load_current_option_positions(start_path);final=load_current_option_positions(end_path)
    plans=recommendations(journal)
    if hashlib.sha256(Path(journal).read_bytes()).hexdigest()!=journal_hash:raise ValueError('Journal changed during projection')
    rows,missing_fees=reconstruct(initial,final,trades,cash,start,end,plans)
    gross=sum(r['gross_period_contribution'] for r in rows);fees=b.total_fees_ytd-a.total_fees_ytd
    itemized=sum(r['fees'] for r in rows);fee_residual=fees-itemized
    other=[r for r in cash if start<local(r['ExecutedAt'])<=end and r['EventType'] not in ('TRD','BAL') and float(r['Amount'])!=0]
    other_cash=sum(float(r['Amount'])-float(r['MiscFees'])-float(r['CommissionsFees']) for r in other)
    actual=b.net_liquidating_value-a.net_liquidating_value
    residual=round(actual-(gross-fees+other_cash),2)
    groups=defaultdict(lambda:{'units':0,'net_period_contribution':0.,'gross':0.,'fees':0.})
    tickers=defaultdict(float)
    for r in rows:
        category=r['link_status']
        if r.get('above_recorded_recommendation_quantity'):category+='__ABOVE_RECORDED_QUANTITY'
        group=groups[category];group['units']+=1;group['net_period_contribution']+=r['net_period_contribution']
        group['gross']+=r['gross_period_contribution'];group['fees']+=r['fees']
        tickers[r['ticker']]+=r['net_period_contribution']
    closed=[r for r in rows if r['status']=='CLOSED'];new_closed=[r for r in closed if r['entry_at'] and r['side']==1]
    entry_groups=defaultdict(list)
    for r in new_closed:entry_groups[(r['entry_at'],r['ticker'],r['expiration'],r['strike'],r['option_type'])].append(r)
    open_groups={(r['entry_at'],r['ticker'],r['expiration'],r['strike'],r['option_type']) for r in rows if r['status']=='OPEN'}
    complete_groups=[q for k,q in entry_groups.items() if k not in open_groups]
    wins=sum(sum(r['net_period_contribution'] for r in q)>0 for q in complete_groups)
    trade_results=[sum(r['net_period_contribution'] for r in q) for q in complete_groups]
    winners=[p for p in trade_results if p>0];losers=[p for p in trade_results if p<0]
    return {'schema_version':1,'basis':'BROKER_PAPER_ACCOUNT_ACTUAL_FILLS_NOT_DIRECTIONAL_PROXY',
        'start':a.as_of_date,'end':b.as_of_date,'beginning':asdict(a),'ending':asdict(b),
        'bridge':{'nav_change':actual,'gross_position_contribution_since_start':gross,
            'broker_realized_gross':b.ytd_pnl-a.ytd_pnl-(b.unrealized_pnl-a.unrealized_pnl),
            'broker_unrealized_change':b.unrealized_pnl-a.unrealized_pnl,'fees':fees,
            'itemized_fees':itemized,'unitemized_fee_residual':fee_residual,'other_cash_net':other_cash,
            'unexplained_nav_residual':residual,'status':'RECONCILED' if residual==0 else 'UNRECONCILED'},
        'groups':dict(groups),'ticker_contributions':dict(sorted(tickers.items(),key=lambda x:x[1],reverse=True)),
        'completed_new_long_entry_groups':len(complete_groups),'winning_new_long_entry_groups':wins,
        'new_long_entry_group_win_rate':wins/len(complete_groups) if complete_groups else None,
        'new_long_trade_payoffs':{'average_winner':sum(winners)/len(winners) if winners else None,
            'average_loser':sum(losers)/len(losers) if losers else None,
            'profit_factor':sum(winners)/-sum(losers) if losers else None,
            'net_closed_trade_pnl':sum(trade_results),'wins':len(winners),'losses':len(losers),
            'flat':sum(p==0 for p in trade_results)},
        'median_closed_new_long_holding_hours':median(max(r['holding_hours'] for r in q) for q in complete_groups) if complete_groups else None,
        'units':rows,'missing_fee_groups':missing_fees,'source_errors':errors,'source_manifest':manifest,
        'other_cash_rows':other,'journal_sha256':journal_hash,
        'limits':['Latest available statement only; intraday account balances after its date are not inferred.',
            'Contract/time matching is inferred: broker statements carry no engine recommendation IDs.',
            'Inherited holdings have unresolved origin and period gains use their beginning mark.',
            'Net contributions include all actual gains/losses; no reviewed error exclusion is applied.',
            'Exit deltas compare original plan references, not verified amended orders or guaranteed alternative fills.',
            'Above-quantity flags compare concurrently open units matched to one plan; they are not automatically execution-error judgments.',
            'Recommendation quantities/fill prices are reference comparisons, not a replayable engine-only return.',
            'Long and short option inventory reconstructed economically; broker TO CLOSE labels do not erase oversells.',
            'Ticker and linked-score results are descriptive, not causal alpha, future probabilities or promotion authority.']}


def connect_hindsight(value,path):
    """Join stock diagnostics to actual closed option entry groups by plan ID.

    This is explicitly secondary to the broker-dollar identity. It never
    substitutes underlying returns for option P/L or assumes the two exits
    happened at the same time.
    """
    csv.field_size_limit(20_000_000)
    outcomes={}
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        for r in csv.DictReader(handle):
            if r.get('Horizon7DStatus')=='COMPLETE':
                ret=num(r.get('Horizon7DDirectionalReturnPct'))
                if ret is not None:outcomes[r['RecommendationID']]=ret
    groups=defaultdict(list)
    open_keys=set()
    for r in value['units']:
        if not r['entry_at'] or r['side']!=1:continue
        k=(r['entry_at'],r['ticker'],r['expiration'],r['strike'],r['option_type'])
        if r['status']=='OPEN':open_keys.add(k)
        else:groups[k].append(r)
    matrix=defaultdict(lambda:{'trade_groups':0,'actual_option_net_pnl':0.})
    joined=0;unknown=0;details=[]
    for k,rows in groups.items():
        if k in open_keys:continue
        ids={r.get('recommendation_id') for r in rows}
        if len(ids)!=1 or None in ids:unknown+=1;continue
        rid=next(iter(ids))
        if rid not in outcomes:unknown+=1;continue
        pnl=sum(r['net_period_contribution'] for r in rows);ret=outcomes[rid]
        label=('OPTION_PROFIT' if pnl>0 else 'OPTION_LOSS_OR_FLAT')+'__'+('STOCK_RIGHT_7D' if ret>0 else 'STOCK_WRONG_OR_FLAT_7D')
        matrix[label]['trade_groups']+=1;matrix[label]['actual_option_net_pnl']+=pnl;joined+=1
        details.append({'ticker':k[1],'entry_at':k[0],'recommendation_id':rid,
            'actual_option_net_pnl':pnl,'stock_directional_return_7d':ret,
            'last_exit_at':max(r['exit_at'] for r in rows),'classification':label})
    value['stock_to_option_bridge']={'source':str(path),'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'matched_closed_entry_groups_with_mature_7d':joined,'unmatched_or_unmatured_groups':unknown,
        'matrix':dict(matrix),'details':details,
        'interpretation':'Actual option exits differ from a fixed seven-session stock checkpoint. Joins inherit inferred recommendation-link limitations; this is not a causal return decomposition.'}
    return value


def markdown(value):
    b=value['bridge'];groups=value['groups']
    lines=['# Actual broker P/L and recommendation attribution','',f"Statement window: **{value['start']} close through {value['end']} close**. PaperMoney broker fills.",
        '',f"**Net account change: ${b['nav_change']:+,.2f}. Reconciliation: {b['status']}; unexplained residual ${b['unexplained_nav_residual']:+,.2f}.**",'',
        '| Account bridge | Dollars |','|---|---:|',
        f"| Realized gross profit/loss from broker totals | ${b['broker_realized_gross']:+,.2f} |",
        f"| Change in open profit/loss | ${b['broker_unrealized_change']:+,.2f} |",
        f"| Actual fees | ${-b['fees']:,.2f} |",
        f"| Actual NAV change | ${b['nav_change']:+,.2f} |",'',
        '## Dollar attribution by evidence quality','',
        'These contributions use beginning marks for inherited positions. They sum to period account change after the separately shown fee/cash residuals. Inferred matches are not confirmed broker intent.',
        '', '| Attribution group | Contract units | Net period contribution |','|---|---:|---:|']
    for name,g in groups.items():lines.append(f"| {name} | {g['units']} | ${g['net_period_contribution']:+,.2f} |")
    lines += ['',f"Additional unitemized fees: ${b['unitemized_fee_residual']:,.2f}; non-trade cash net: ${b['other_cash_net']:+,.2f}.",
        '', '## Actual closed long trades','',
        f"New long-option entry groups fully closed: {value['completed_new_long_entry_groups']}; profitable groups: {value['winning_new_long_entry_groups']}. This counts opening fill/contract groups, not research episodes. Unfinished entry groups are excluded.",
        f"Actual long-trade payoff summary: {value['new_long_trade_payoffs']}.",
        '', '## Ticker contributions','', '| Ticker | Net period contribution |','|---|---:|']
    for ticker,pnl in value['ticker_contributions'].items():lines.append(f'| {ticker} | ${pnl:+,.2f} |')
    if value.get('stock_to_option_bridge'):
        bridge=value['stock_to_option_bridge']
        lines+=['','## Why stock-direction outcomes differ from actual option dollars','',
            f"Matched fully closed entry groups with matured seven-session stock outcomes: {bridge['matched_closed_entry_groups_with_mature_7d']}. Unmatched or not matured: {bridge['unmatched_or_unmatured_groups']}.",
            '', '| Actual option result versus seven-session stock result | Entry groups | Actual net option P/L |','|---|---:|---:|']
        for name,g in bridge['matrix'].items():lines.append(f"| {name} | {g['trade_groups']} | ${g['actual_option_net_pnl']:+,.2f} |")
        lines+=['',bridge['interpretation']]
    lines+=['','## What this establishes','',
        'Actual option dollars can differ from fixed-seven-session stock direction because entries, contract payoffs, sizing and realized exits differ. This report reconciles broker dollars and links available plans; it does not prove which component causally generated an edge.',
        '', '## Limitations','',*[f'- {x}' for x in value['limits']],
        '',f"Source parse errors: {value['source_errors']}. Missing fill-fee groups: {value['missing_fee_groups']}."]
    return '\n'.join(lines)


def write(value,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,text in [('attribution.json',json.dumps(value,indent=2)),('attribution.md',markdown(value))]:
        target=output/name
        with target.open('x',encoding='utf-8') as handle:handle.write(text)
    fields=sorted(set(k for r in value['units'] for k in r))
    with (output/'contract_units.csv').open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in value['units']:writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--statements',type=Path,required=True)
    parser.add_argument('--journal',type=Path,default=Path('data/trade_journal.csv'))
    parser.add_argument('--beginning',required=True,help='Starting statement filename, measured at close')
    parser.add_argument('--ending',required=True,help='Ending statement filename, measured at close')
    parser.add_argument('--hindsight',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=build(args.statements,args.journal,args.beginning,args.ending)
    if args.hindsight:connect_hindsight(value,args.hindsight)
    write(value,args.output)
    print(json.dumps(value['bridge'],indent=2))
