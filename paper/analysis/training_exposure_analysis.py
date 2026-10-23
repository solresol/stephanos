#!/usr/bin/env python3
"""Audit dated training-exposure candidates and paired benchmark differences.

The --snapshot operation is read-only. Analysis thereafter uses frozen inputs,
never calls a model, and never changes reference translations or benchmark rows.
Run with uv run; see paper/analysis/README.md for the required frozen inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import unicodedata

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import linear_sum_assignment
from sacrebleu.metrics import CHRF

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CUTOFF = pd.Timestamp('2026-02-16T00:00:00Z')
RNG_SEED = 20260921
METRICS = ['bleu4', 'chrfpp', 'meteor', 'rouge_l', 'mean_lexical']


def snapshot(out: Path, release: Path):
    os.environ.setdefault('DB_HOST', 'raksasa')
    os.environ.setdefault('DB_USER', 'stephanos')
    from db import get_connection
    refs = pd.read_csv(release / 'approved_reference_translations.csv')
    ids = refs.lemma_id.astype(int).tolist()
    queries = {
        'all_entry_dates': """SELECT a.id AS lemma_id,a.billerbeck_id,a.lemma,a.version,
          a.created_at AS lemma_created_at,a.translated_at,a.translation_prompt_version,
          a.quarantined,min(r.completed_at) FILTER (WHERE r.translation_text IS NOT NULL
          AND r.status != 'failed') AS first_run_completed_at,
          min(h.created_at) AS first_human_record_created_at
          FROM assembled_lemmas a LEFT JOIN translation_runs r ON r.lemma_id=a.id
          LEFT JOIN human_translations h ON h.lemma_id=a.id GROUP BY a.id ORDER BY a.id""",
        'early_runs': """SELECT r.id AS run_id,r.lemma_id,r.model,r.status,r.translation_text,
          r.created_at,r.completed_at,r.public_eligible,r.public_block_reason,
          r.source_text_version_id,s.source_document,s.text_body AS source_text,
          p.name AS profile_name,v.version AS prompt_version,
          q.created_by AS request_created_by,q.started_at,q.finished_at
          FROM translation_runs r JOIN translation_prompt_profiles p ON p.id=r.profile_id
          JOIN translation_prompt_profile_versions v ON v.id=r.profile_version_id
          JOIN lemma_source_text_versions s ON s.id=r.source_text_version_id
          JOIN translation_run_requests q ON q.id=r.request_id
          WHERE r.completed_at < TIMESTAMPTZ '2026-02-18 00:00:00+00'
          AND COALESCE(r.translation_text,'')!='' AND r.status!='failed' ORDER BY r.id""",
        'human_records': """SELECT h.id,h.lemma_id,h.stage,h.status,h.created_at,h.updated_at,
          h.reviewed_at,h.derived_from_run_id,h.translation_text
          FROM human_translations h ORDER BY h.id""",
        'prompt_dates': 'SELECT version,created_at,notes FROM translation_prompts ORDER BY version',
        'benchmark_runs': """SELECT r.id AS run_id,r.lemma_id,r.model,r.status,r.created_at,
          r.completed_at,r.source_text_version_id,p.name AS profile_name,
          v.version AS prompt_version FROM translation_runs r
          JOIN translation_prompt_profiles p ON p.id=r.profile_id
          JOIN translation_prompt_profile_versions v ON v.id=r.profile_version_id
          WHERE r.lemma_id=ANY(%s) ORDER BY r.id""",
    }
    conn = get_connection(dict_cursor=True)
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    result = {'queries': queries}
    with conn.cursor() as cur:
        cur.execute('SELECT now() AS captured_at,current_database() AS database,current_setting(\'TimeZone\') AS database_timezone')
        result['metadata'] = dict(cur.fetchone())
        for name, sql in queries.items():
            cur.execute(sql, (ids,) if name == 'benchmark_runs' else None)
            result[name] = [dict(r) for r in cur.fetchall()]
    conn.rollback()
    conn.close()
    (out / 'database_snapshot.json').write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    for name in ['approved_reference_translations.csv', 'llm_outputs_v1_v2_v3.csv', 'model_prompt_cell_summary.csv']:
        shutil.copyfile(release / name, out / name)


def greek_words(text):
    return sum(any('GREEK' in unicodedata.name(c, '') and unicodedata.category(c).startswith('L')
                   for c in w) for w in unicodedata.normalize('NFC', text).split())


def norm(text):
    return ' '.join(unicodedata.normalize('NFC', str(text)).casefold().split())


def tokens(text):
    return re.findall(r'\w+', unicodedata.normalize('NFC', text).casefold())


def headword_key(text):
    # Only Unicode diacritics and case are normalised; no fuzzy matching.
    return ''.join(c for c in unicodedata.normalize('NFD', text).casefold()
                   if not unicodedata.combining(c))


def recover_log_dates(out, refs):
    messages=json.loads((out/'early_cron_messages.json').read_text())
    events=[]
    for message in messages:
        completed_by=pd.Timestamp(message['date'])
        if completed_by>=CUTOFF:
            continue
        model_match=re.search(r'Step \d+: Translating lemmas with ([^.\s]+(?:\.[\d]+)?)\.\.\.',message['body'])
        model=model_match[1] if model_match else 'not recorded'
        version_match=re.search(r'Using translation prompt version (\d+)',message['body'])
        version=version_match[1] if version_match else 'unversioned predecessor'
        for line in message['body'].splitlines():
            match=re.match(r'Translating (.+?) \(#(\d+)\).*?\.\.\. OK \(tokens:',line)
            if match:
                events.append(dict(headword=match[1],entry_number=int(match[2]),
                    headword_key=headword_key(match[1]),completed_by_utc=str(completed_by.tz_convert('UTC')),
                    email_date=message['date'],email_id=message['id'],model=model,
                    prompt_version=version,evidence_line=line))
    events=pd.DataFrame(events).sort_values('completed_by_utc')
    events.to_csv(out/'successful_pre_cutoff_log_events.csv',index=False)
    identity=['entry_number','headword_key']
    first=events.drop_duplicates(identity,keep='first').copy()
    counts=events.groupby(identity).size().rename('logged_success_count').reset_index()
    first=first.merge(counts,on=identity,validate='one_to_one')
    first.to_csv(out/'all_corpus_log_candidates.csv',index=False)
    matched=[]
    for _,r in refs.iterrows():
        hits=events[(events.entry_number==r.entry_number)&(events.headword_key==headword_key(r.headword))]
        assert len(hits)>0, f'No dated successful log for {r.lemma_id}'
        f=hits.iloc[0]
        explicit=hits[hits.prompt_version=='1']
        matched.append(dict(lemma_id=int(r.lemma_id),first_documented_translation_by=f.email_date,
            first_documented_model=f.model,first_documented_prompt=f.prompt_version,
            first_evidence_email_id=f.email_id,first_evidence_line=f.evidence_line,
            first_explicit_v1_by=explicit.iloc[0].email_date if len(explicit) else '',
            logged_success_count=len(hits),log_identity_match='accent-normalised headword AND entry number'))
    matched=pd.DataFrame(matched)
    matched.to_csv(out/'benchmark_log_dates.csv',index=False)
    return matched,dict(messages_examined=len(messages),successful_entry_events=len(events),
                       distinct_log_identities=len(first),benchmark_matches=len(matched),
                       explicit_v1_benchmark_matches=int(matched.first_explicit_v1_by.ne('').sum()))


def overlap(a, b):
    from difflib import SequenceMatcher
    x, y = tokens(a), tokens(b)
    return SequenceMatcher(None, x, y, autojunk=False).find_longest_match().size


def hc3(y, x):
    """OLS, HC3 covariance, residual-df Student t intervals (approximate)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    assert np.linalg.matrix_rank(x) == x.shape[1]
    inv = np.linalg.inv(x.T @ x)
    beta = inv @ x.T @ y
    resid = y - x @ beta
    hat = np.sum((x @ inv) * x, axis=1)
    cov = inv @ (x.T @ (x * (resid / (1 - hat))[:, None] ** 2)) @ inv
    se = np.sqrt(np.diag(cov))
    df = len(y) - x.shape[1]
    crit = stats.t.ppf(.975, df)
    return {'estimate': float(beta[1]), 'se': float(se[1]),
            'ci_low': float(beta[1] - crit * se[1]), 'ci_high': float(beta[1] + crit * se[1]),
            'p': float(2 * stats.t.sf(abs(beta[1] / se[1]), df)),
            'n': len(y), 'df': df, 'max_leverage': float(hat.max())}


def adjusted(y, exposed, length, extra=None, permutations=0):
    z = np.log(np.asarray(length, float))
    z -= z.mean()
    nuisance = np.column_stack([np.ones(len(z)), z])
    if extra is not None:
        nuisance = np.column_stack([nuisance, extra])
    x = np.column_stack([nuisance[:, 0], np.asarray(exposed, float), nuisance[:, 1:]])
    result = hc3(y, x)
    if permutations:
        # Freedman-Lane residual permutation; assumes exchangeable null residuals.
        rng = np.random.default_rng(RNG_SEED)
        yy = np.asarray(y, float)
        fitted = nuisance @ np.linalg.lstsq(nuisance, yy, rcond=None)[0]
        residuals = yy - fitted
        weight = np.linalg.pinv(x)[1]
        observed = abs(float(weight @ yy))
        exceed = 0
        for _ in range(permutations // 1000):
            orders = np.argsort(rng.random((1000, len(yy))), axis=1)
            betas = (fitted[None, :] + residuals[orders]) @ weight
            exceed += np.count_nonzero(np.abs(betas) >= observed - 1e-12)
        result['residual_permutation_p'] = float((exceed + 1) / (permutations + 1))
        result['permutations'] = permutations
    return result


def group_test(y, exposed, permutations=50000):
    yy, ee = np.asarray(y, float), np.asarray(exposed, bool)
    a, b = yy[ee], yy[~ee]
    v1, v0 = a.var(ddof=1)/len(a), b.var(ddof=1)/len(b)
    se = np.sqrt(v1 + v0)
    df = (v1+v0)**2 / (v1**2/(len(a)-1)+v0**2/(len(b)-1))
    diff = a.mean()-b.mean()
    ci = stats.t.ppf(.975, df)*se
    rng = np.random.default_rng(RNG_SEED)
    exceed=0
    for _ in range(permutations//1000):
        perm = yy[np.argsort(rng.random((1000,len(yy))), axis=1)]
        d = perm[:, :len(a)].mean(1)-perm[:, len(a):].mean(1)
        exceed += np.count_nonzero(np.abs(d) >= abs(diff)-1e-12)
    return dict(n_early=len(a), n_other=len(b), early_mean=float(a.mean()), other_mean=float(b.mean()),
                difference=float(diff),ci_low=float(diff-ci),ci_high=float(diff+ci),
                welch_p=float(stats.ttest_ind(a,b,equal_var=False).pvalue),
                mannwhitney_p=float(stats.mannwhitneyu(a,b,alternative='two-sided').pvalue),
                permutation_p=(exceed+1)/(permutations+1))


def paired_test(y):
    y = np.asarray(y,float)
    test = stats.ttest_1samp(y, 0)
    width = stats.t.ppf(.975,len(y)-1)*stats.sem(y)
    return dict(n=len(y),mean=float(y.mean()),median=float(np.median(y)),
                ci_low=float(y.mean()-width),ci_high=float(y.mean()+width),p=float(test.pvalue),
                wilcoxon_p=float(stats.wilcoxon(y).pvalue),positive=int((y>0).sum()))


def holm(pvalues):
    order=np.argsort(pvalues); result=np.empty(len(order)); last=0
    for i,k in enumerate(order):
        last=max(last,min(1.,pvalues[k]*(len(order)-i)));result[k]=last
    return result.tolist()


def analyse(out):
    snap=json.loads((out/'database_snapshot.json').read_text())
    refs=pd.read_csv(out/'approved_reference_translations.csv').sort_values('entry_number')
    rows=pd.read_csv(out/'llm_outputs_v1_v2_v3.csv')
    assert len(refs)==100 and refs.lemma_id.is_unique and len(rows)==4500
    assert not rows.duplicated(['profile_name','prompt_version','lemma_id']).any()
    assert rows.groupby(['profile_name','prompt_version']).size().eq(100).all()
    assert np.allclose(rows[METRICS[:4]].mean(axis=1),rows.mean_lexical,atol=1e-12)
    assert set(refs.lemma_id)==set(rows.lemma_id)
    assert rows.groupby('lemma_id').human_translation_text.nunique().eq(1).all()
    assert rows.groupby('lemma_id').source_text.nunique().eq(1).all()
    for _,r in refs.iterrows():
        match=rows[rows.lemma_id==r.lemma_id].iloc[0]
        assert match.human_translation_text == r.approved_english_translation
        assert match.source_text == r.greek_source_as_run
    logdates,logstats=recover_log_dates(out,refs)
    er=pd.DataFrame(snap['early_runs'])
    er['time']=pd.to_datetime(er.completed_at,utc=True)
    er=er[er.time<CUTOFF].copy()
    hr=pd.DataFrame(snap['human_records'])
    hr['time']=pd.to_datetime(hr.created_at,utc=True)
    hr=hr[hr.time<CUTOFF].copy()
    ai=set(er.lemma_id);human=set(hr.lemma_id)
    dated=refs[['lemma_id','entry_number','headword']].copy()
    dated['greek_words']=refs.greek_source_as_run.map(greek_words)
    dated['reference_words']=refs.approved_english_translation.map(lambda t:len(t.split()))
    dated['early_ai']=dated.lemma_id.isin(ai)
    dated['early_human_record']=dated.lemma_id.isin(human)
    dated['either_early']=dated.early_ai | dated.early_human_record
    dated['greta_three']=dated.entry_number.isin([2,3,82])
    dated['quotation']=refs.greek_source_as_run.str.contains('“[^”]+”',regex=True).astype(int)
    earliest=er.groupby('lemma_id').time.min().to_dict()
    humanfirst=hr.groupby('lemma_id').time.min().to_dict()
    dated['first_early_ai_utc']=dated.lemma_id.map(earliest)
    dated['first_early_human_record_utc']=dated.lemma_id.map(humanfirst)
    runs=er.groupby('lemma_id').run_id.apply(lambda x:','.join(map(str,x))).to_dict()
    dated['early_run_ids']=dated.lemma_id.map(runs).fillna('')
    dated=dated.merge(logdates,on='lemma_id',validate='one_to_one')
    dated['december_documented']=pd.to_datetime(dated.first_documented_translation_by,utc=True)<pd.Timestamp('2026-01-01T00:00:00Z')
    benchmark_ids=set(refs.lemma_id)
    dates=pd.DataFrame(snap['all_entry_dates'])
    all_candidates=dates[dates.lemma_id.isin(ai|human)].copy()
    all_candidates['early_ai']=all_candidates.lemma_id.isin(ai)
    all_candidates['early_human_record']=all_candidates.lemma_id.isin(human)
    all_candidates['in_benchmark']=all_candidates.lemma_id.isin(benchmark_ids)
    all_candidates['first_early_ai_utc']=all_candidates.lemma_id.map(earliest)
    all_candidates['first_early_human_record_utc']=all_candidates.lemma_id.map(humanfirst)
    all_candidates['early_run_ids']=all_candidates.lemma_id.map(runs).fillna('')
    all_candidates.to_csv(out/'database_dated_candidates.csv',index=False)
    for model,label in [('gpt-5.6-sol','sol'),('gpt-5.5','gpt55')]:
        for version in [1,2,3]:
            sub=rows[(rows.profile_name==model)&(rows.prompt_version==version)].set_index('lemma_id')
            assert len(sub)==100 and sub.index.is_unique
            for m in METRICS:
                dated[f'{label}_v{version}_{m}']=dated.lemma_id.map(sub[m])*100
    for v in [1,2,3]:
        for m in METRICS:
            dated[f'delta_v{v}_{m}']=dated[f'sol_v{v}_{m}']-dated[f'gpt55_v{v}_{m}']
    dated['cohort']=np.select([dated.early_ai,dated.early_human_record],
                            ['Dated AI output','Early human record'],default='No surviving pre-cutoff record')
    dated.to_csv(out/'entry_analysis.csv',index=False)
    dated.to_csv(out/'candidate_entries.csv',index=False)
    er.drop(columns='time').to_csv(out/'early_ai_runs.csv',index=False)
    hr.drop(columns='time').to_csv(out/'early_human_records.csv',index=False)
    analysis={'cutoff':'2026-02-16T00:00:00Z','seed':RNG_SEED,
              'cohort_counts':{'benchmark':100,'early_ai_runs':len(er),'early_ai_entries':len(ai),
                               'early_human_records':len(hr),'early_human_entries':len(human),
                               'union':len(ai|human),'overlap':len(ai&human),
                               'benchmark_early_ai':len(ai&benchmark_ids),
                               'benchmark_early_human':len(human&benchmark_ids),
                               'benchmark_union':len((ai|human)&benchmark_ids)},
              'metadata':snap['metadata'],'prompt_dates':snap['prompt_dates'],'log_recovery':logstats,
              'interpretation':'All 100 benchmark entries have pre-cutoff translation logs. No unexposed comparison group. Early-run cohorts below describe survival of database records, not training exposure.',
              'primary':{},'cohort_sensitivity':{},'length_sensitivity':{},'metric_sensitivity':{},
              'paired':{},'diagnostics':{},'historical_similarity':{}}
    for cohort in ['early_ai','early_human_record','either_early','greta_three','december_documented']:
        ee=dated[cohort]
        values={}
        for v in [1,2,3]:
            y=dated[f'delta_v{v}_mean_lexical']
            values[f'v{v}']={'gain_difference':group_test(y,ee),
                            'adjusted_gain_difference':adjusted(y,ee,dated.greek_words,permutations=50000),
                            'sol_score_difference':group_test(dated[f'sol_v{v}_mean_lexical'],ee),
                            'gpt55_score_difference':group_test(dated[f'gpt55_v{v}_mean_lexical'],ee),
                            'paired_early':paired_test(y[ee]),'paired_other':paired_test(y[~ee])}
        values['lengths']={'early':dated[ee].greek_words.describe().to_dict(),
                          'other':dated[~ee].greek_words.describe().to_dict()}
        analysis['cohort_sensitivity'][cohort]=values
    analysis['primary']=analysis['cohort_sensitivity']['early_ai']
    for v in [1,2,3]:
        y=dated[f'delta_v{v}_mean_lexical'];ee=dated.early_ai
        analysis['paired'][f'v{v}']=paired_test(y)
        analysis['paired'][f'v{v}']['sol_mean']=float(dated[f'sol_v{v}_mean_lexical'].mean())
        analysis['paired'][f'v{v}']['gpt55_mean']=float(dated[f'gpt55_v{v}_mean_lexical'].mean())
        loglength=np.log(dated.greek_words);loglength-=loglength.mean()
        length_models={
            'log_length_quadratic':adjusted(y,ee,dated.greek_words,extra=loglength**2),
            'log_length_and_quotation':adjusted(y,ee,dated.greek_words,extra=dated.quotation),
            'reference_length':adjusted(y,ee,dated.reference_words),
            'raw_greek_length':hc3(y,np.column_stack([np.ones(100),ee,dated.greek_words])),
            'baseline_score_sensitivity':adjusted(y,ee,dated.greek_words,extra=dated[f'gpt55_v{v}_mean_lexical']),
        }
        estimates=[]
        for i in dated.index:
            ix=dated.index!=i
            estimates.append(adjusted(y[ix],ee[ix],dated.greek_words[ix])['estimate'])
        length_models['leave_one_out_range']=[min(estimates),max(estimates)]
        analysis['length_sensitivity'][f'v{v}']=length_models
        for m in METRICS[:4]:
            analysis['metric_sensitivity'][f'v{v}_{m}']=adjusted(dated[f'delta_v{v}_{m}'],ee,dated.greek_words)
    ps=[analysis['primary'][f'v{v}']['adjusted_gain_difference']['p'] for v in [1,2,3]]
    for v,p in zip([1,2,3],holm(ps)):
        analysis['primary'][f'v{v}']['adjusted_gain_difference']['holm_p_across_prompts']=p
    ps=[x['p'] for x in analysis['metric_sensitivity'].values()]
    for x,p in zip(analysis['metric_sensitivity'].values(),holm(ps)):x['holm_p_12_tests']=p
    a,b=dated[dated.early_ai],dated[~dated.early_ai]
    distances=np.abs(np.log(a.greek_words.to_numpy())[:,None]-np.log(b.greek_words.to_numpy())[None,:])
    cost=distances.copy();cost[distances>np.log(1.25)]+=1000
    ii,jj=linear_sum_assignment(cost)
    pairs=[]
    for i,j in zip(ii,jj):
        if distances[i,j]<=np.log(1.25):
            aa,bb=a.iloc[i],b.iloc[j]
            pairs.append({'early_entry':int(aa.entry_number),'control_entry':int(bb.entry_number),
                          'early_words':int(aa.greek_words),'control_words':int(bb.greek_words),
                          'gain_difference':aa.delta_v1_mean_lexical-bb.delta_v1_mean_lexical})
    pd.DataFrame(pairs).to_csv(out/'length_matched_pairs.csv',index=False)
    analysis['length_matched_v1']=paired_test([p['gain_difference'] for p in pairs])
    # Comparing outputs directly to the actual surviving early AI drafts tests
    # convergence toward possible synthetic training targets, separately from
    # similarity to the much later human reference.
    chrf=CHRF(word_order=2)
    historical=[]
    for _,e in er.iterrows():
        if e.lemma_id not in benchmark_ids:
            continue
        ref=refs[refs.lemma_id==e.lemma_id].iloc[0]
        rr={'early_run_id':int(e.run_id),'lemma_id':int(e.lemma_id),'entry_number':int(ref.entry_number),
            'same_source':norm(e.source_text)==norm(ref.greek_source_as_run),
            'early_status':e.status,'early_source_document':e.source_document}
        for model,label in [('gpt-5.6-sol','sol'),('gpt-5.5','gpt55')]:
            r=rows[(rows.lemma_id==e.lemma_id)&(rows.profile_name==model)&(rows.prompt_version==1)].iloc[0]
            rr[label+'_chrf_to_early']=chrf.sentence_score(r.ai_translation_text,[e.translation_text]).score
            rr[label+'_exact_to_early']=norm(r.ai_translation_text)==norm(e.translation_text)
            rr[label+'_longest_shared_tokens']=overlap(r.ai_translation_text,e.translation_text)
        rr['chrf_delta']=rr['sol_chrf_to_early']-rr['gpt55_chrf_to_early']
        historical.append(rr)
    hist=pd.DataFrame(historical)
    hist.to_csv(out/'historical_draft_similarity.csv',index=False)
    same=hist[hist.same_source].sort_values('early_run_id').drop_duplicates('lemma_id',keep='last')
    analysis['historical_similarity']={'all_runs':len(hist),'same_source_runs':int(hist.same_source.sum()),
        'same_source_entries':len(same),'paired_chrf_delta':paired_test(same.chrf_delta),
        'sol_exact_count':int(same.sol_exact_to_early.sum()),'gpt55_exact_count':int(same.gpt55_exact_to_early.sum()),
        'sol_chrf_mean':float(same.sol_chrf_to_early.mean()),'gpt55_chrf_mean':float(same.gpt55_chrf_to_early.mean())}
    strict=dated[~dated.early_ai | dated.lemma_id.isin(same.lemma_id)]
    analysis['strict_source_v1']=adjusted(strict.delta_v1_mean_lexical,strict.early_ai,strict.greek_words)
    exact=[]
    for v in [1,2,3]:
        for model in ['gpt-5.5','gpt-5.6-sol']:
            r=rows[(rows.profile_name==model)&(rows.prompt_version==v)]
            e=r.lemma_id.isin(ai)
            for flag in ['exact_normalized','near_normalized_98']:
                yes=r[flag].map(lambda x:str(x).lower()=='true')
                table=[[int((yes&e).sum()),int((~yes&e).sum())],
                       [int((yes&~e).sum()),int((~yes&~e).sum())]]
                exact.append(dict(model=model,version=v,flag=flag,table=table,p=float(stats.fisher_exact(table).pvalue)))
    analysis['exact_match_diagnostics']=exact
    # With universal dated eligibility, the requested exposure coefficient is
    # non-identifiable. Test general differential gains with length separately.
    analysis['gain_length_slope']={}
    log2length=np.log2(dated.greek_words)
    for v in [1,2,3]:
        analysis['gain_length_slope'][f'v{v}']=hc3(dated[f'delta_v{v}_mean_lexical'],
                                                np.column_stack([np.ones(100),log2length]))
    timeline=[]
    cells=pd.read_csv(out/'model_prompt_cell_summary.csv')
    for (model,v),r in rows[rows.provider=='OpenAI'].groupby(['profile_name','prompt_version']):
        e=r.lemma_id.isin(ai)
        timeline.append(dict(model=model,prompt_version=int(v),n_early=int(e.sum()),
            early_mean=100*r.loc[e,'mean_lexical'].mean(),other_mean=100*r.loc[~e,'mean_lexical'].mean(),
            all_mean=100*r.mean_lexical.mean(),
            release_date=cells[(cells.profile_name==model)&(cells.prompt_version==v)].release_date.iloc[0]))
    pd.DataFrame(timeline).sort_values(['release_date','prompt_version']).to_csv(out/'model_timeline.csv',index=False)
    named=rows[rows.entry_number.isin([2,3,82,30])].copy()
    named.to_csv(out/'named_examples_all_outputs.csv',index=False)
    dates=pd.DataFrame(snap['all_entry_dates'])
    analysis['diagnostics']={'database_entries':len(dates),'benchmark_greek_words':int(dated.greek_words.sum()),
        'all_metric_rows':len(rows),'model_prompt_cells':45,
        'earliest_run_utc':str(er.time.min()),'all_early_models':sorted(er.model.unique().tolist()),
        'all_early_prompt_versions':er.prompt_version.unique().tolist(),
        'source_mismatch_early_runs':hist[~hist.same_source].early_run_id.tolist(),
        'cutoff_day_inclusion_changes_candidates':False,
        'no_pre_gpt55_cutoff_surviving_runs':bool((er.time>=pd.Timestamp('2025-12-01T00:00:00Z')).all())}
    numbered=refs.merge(dates[['lemma_id','billerbeck_id']],on='lemma_id',validate='one_to_one')
    mismatches=numbered[numbered.billerbeck_id!='Κ'+numbered.entry_number.astype(str)]
    analysis['diagnostics']['numbering_discrepancies']=mismatches[['lemma_id','entry_number','headword','billerbeck_id']].to_dict('records')
    analysis['surviving_run_comparison']=analysis.pop('primary')
    # An explicit cutoff-day/time-zone check, not merely an assumption.
    all_early=pd.to_datetime(pd.DataFrame(snap['early_runs']).completed_at,utc=True)
    bounds=[pd.Timestamp('2026-02-15T10:00:00Z'),pd.Timestamp('2026-02-17T12:00:00Z')]
    assert ((all_early>=bounds[0])&(all_early<=bounds[1])).sum()==0
    assert not ((pd.to_datetime(pd.DataFrame(snap['human_records']).created_at,utc=True)>=CUTOFF)&
                (pd.to_datetime(pd.DataFrame(snap['human_records']).created_at,utc=True)<bounds[1])).any()
    (out/'analysis.json').write_text(json.dumps(analysis,ensure_ascii=False,indent=2))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.suffix in ['.csv','.json']}
    (out/'input_and_output_sha256.json').write_text(json.dumps(hashes,indent=2))
    print(json.dumps({'counts':analysis['cohort_counts'],'log_recovery':analysis['log_recovery'],
                      'paired':analysis['paired'],'historical':analysis['historical_similarity']},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--release',type=Path)
    p.add_argument('--snapshot',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.snapshot:
        if not a.release:p.error('--snapshot requires --release')
        snapshot(a.output,a.release)
    analyse(a.output)


if __name__=='__main__':main()
