"""Compact gate summary for one replay file: first-edit slip / malformation rates baseline vs (i) vs (ii) with CIs."""
import json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_replay as AR


def fmt(d):
    lo, hi = d['wilson95']
    return f"{d['k']}/{d['n']} = {100*d['rate']:.2f}% [{100*lo:.2f}, {100*hi:.2f}]"


def rr(d):
    lo, hi = d['boot95']
    return f"{100*d['point']:.1f}% [{100*lo:.1f}, {100*hi:.1f}]" if d['point'] == d['point'] else 'n/a'


path = sys.argv[1]
out = {}
for subset in (None, 'natural'):
    for tau in (0.0, 1.0, 2.0):
        r = AR.summarize(path, os.path.join(HERE, 'data/replay_first_edit.jsonl'), tau=tau, B=2000, subset=subset)
        key = f"{subset or 'all'}|tau={tau}"
        out[key] = r
        if tau == 0.0:
            print(f"== {os.path.basename(path)} subset={subset or 'all'}: contexts={r['n_contexts']} edit calls={r['n_edit_calls']} "
                  f"(natural {r['natural_edit']}, forced {r['forced_edit']}); status={r['status']}")
            print('  baseline slip            ', fmt(r['base_slip']))
            print('  baseline census-malformed', fmt(r['base_census_bad']))
            print('  baseline strict-invalid  ', fmt(r['base_strict_bad']), ' silent (census-ok but strict-invalid):', fmt(r['base_silent']))
            print('  (i)  slip after          ', fmt(r['i_nc_slip']), ' rel.red.', rr(r['relred']['slip_i_nc']))
            print('  (i)  census-malformed    ', fmt(r['i_nc_census_bad']), ' rel.red.', rr(r['relred']['census_i_nc']))
            print('  (i)  strict-invalid      ', fmt(r['i_nc_strict_bad']), ' rel.red.', rr(r['relred']['strict_i_nc']))
            print('  (i)max slip after        ', fmt(r['i_max_slip']), ' rel.red.', rr(r['relred']['slip_i_max']))
            print('  (i+) census-malformed    ', fmt(r['iplus_census_bad']), ' rel.red.', rr(r['relred']['census_iplus']))
            print('  (i+) strict-invalid      ', fmt(r['iplus_strict_bad']), ' rel.red.', rr(r['relred']['strict_iplus']))
            for nm in ('slip_i_nc', 'census_i_nc', 'census_iplus', 'census_ipp', 'census_ii', 'slip_i_max'):
                d = r['paired'][nm]
                if d['before']:
                    print(f"  paired {nm:13s}: before {d['before']}, still {d['still_positive']}, new {d['new_positive']} -> rel.red. "
                          f"{100*d['relred_point']:.1f}% Wilson95 [{100*d['relred_wilson95'][0]:.1f}, {100*d['relred_wilson95'][1]:.1f}]")
            fr = r['false_repair_real']
            print(f"  false repairs on valid calls: (i) {fr['i_changed_valid']}/{fr['n_valid']} Wilson95 upper {100*fr['wilson95_i'][1]:.2f}%, (i+) {fr['iplus_changed_valid']}/{fr['n_valid']}, (ii) {fr['ii_changed_valid']}/{fr['n_valid']}")
            c = r['cost_i']
            print(f"  (i) cost: interventions={c['interventions']} rounds={c['rounds_hist']} amortized extra tokens/edit={c['amortized_extra_tokens_per_edit_call']:.2f} "
                  f"extra requests/edit={c['amortized_extra_requests_per_edit_call']:.3f} extra latency/edit={c['amortized_extra_latency_per_edit_call_s']:.3f}s")
        print(f"  (ii) tau={tau}: slip after {fmt(r['ii_slip'])} rel.red. {rr(r['relred']['slip_ii'])}; census-malformed {fmt(r['ii_census_bad'])} "
              f"rel.red. {rr(r['relred']['census_ii'])}; abstain {fmt(r['ii_abstain'])}")
json.dump(out, open(os.path.join(HERE, 'out', 'gate_' + os.path.basename(path).replace('.jsonl', '.json')), 'w'), indent=1, default=str)
