# Catalogue review checklist

These 18 records are research drafts, not published facts. A human reviewer must open every
official source and compare it with the matching JSON before running `janmitra-seed` with
`--confirm-reviewed`.

Original draft date: **2026-09-07**. Automated source updates through **2026-10-09**
are documented in `SOURCE-CHECK-2026-10-09.md`; a named human review is still required.

The stable file and slug `mgnrega` now refer to the current **VB-G RAM G** programme.
MGNREGA was replaced with effect from 1 July 2026; the current guarantee is 125 days
per eligible rural household per financial year. The old name and 100-day search phrase
remain aliases for compatibility, not claims that the old guarantee is current.

| Record | Official source | High-risk details to check |
| --- | --- | --- |
| `apy.json` | [PFRDA APY](https://pfrda.org.in/web/pfrda/schemes/atal-pension-yojana-apy) | Entry age, tax-payer exclusion, pension choices, contribution rules |
| `day-nrlm.json` | [Ministry of Rural Development report](https://rural.gov.in/sites/default/files/State_Performance_Report_2023-2024_22102024.pdf) | Current target group, local availability, fund and interest-support wording |
| `kcc.json` | [myScheme KCC](https://www.myscheme.gov.in/schemes/kcc) | Interest support, security thresholds, eligible farmer types, documents |
| `mgnrega.json` | [VB-G RAM G in force](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2292527&lang=1&reg=6), [transition FAQ](https://www.pib.gov.in/FaqDetails.aspx?ModuleId=4&NoteId=158511&lang=1&reg=3) | Replacement from 1 July 2026, 125 household days, existing-card/eKYC transition, local wages and work-demand process |
| `nsap.json` | [NSAP guidelines](https://rural.gov.in/sites/default/files/NSAP_Guidelines_English.pdf) | Active components, BPL definition, central amounts, state additions |
| `pm-jay.json` | [NHA beneficiary rights](https://nha.gov.in/img/resources/Adhikar-Patra.pdf), [senior-citizen FAQ](https://nha.gov.in/img/resources/English_FAQs_related_to_the_benefits_for_senior_citizens.pdf) | Current beneficiary databases, coverage, packages, senior-citizen expansion |
| `pm-kisan.json` | [PM-KISAN portal](https://pmkisan.gov.in/) | Annual benefit, family definition, exclusions, eKYC and registration status |
| `pm-sym.json` | [Labour Ministry FAQ](https://labour.gov.in/FAQ-0) | Entry age, income ceiling, exclusions, pension and contributions |
| `pm-vishwakarma.json` | [MSME scheme booklet](https://msme.gov.in/sites/default/files/Scheme-booklet-Eng.pdf) | Notified trades, benefit stages, loan terms, family and prior-loan exclusions |
| `pmay-g.json` | [PMAY-G self-check](https://pmayg.dord.gov.in/netiayHome/questions.html) | Current survey window, automatic inclusions/exclusions, selection process |
| `pmegp.json` | [Revised PMEGP guidelines](https://www.kviconline.gov.in/pmegpeportal/dashboard/notification/Revised_PMEGP_Scheme_Guidelines_07122023_compressed.pdf) | Confirm post-2025-26 continuation before publishing; project limits and subsidy rules |
| `pmfby.json` | [PMFBY guidelines](https://pmfby.gov.in/guidelines) | Current operational guideline, notified crops/areas, deadlines, premiums and risks |
| `pmgkay.json` | [myScheme PMGKAY](https://www.myscheme.gov.in/schemes/pm-gkay?_x_tr_hist=true) | Current continuation period, AAY/PHH quantities and state identification |
| `pmjdy.json` | [PMJDY scheme details](https://pmjdy.gov.in/scheme) | KYC alternatives, accident-cover conditions, overdraft limit and eligibility |
| `pmjjby.json` | [DFS PMJJBY](https://www.financialservices.gov.in/pmjjby) | Entry/exit ages, premium, lien period, cover and auto-debit terms |
| `pmmy.json` | [DFS PMMY](https://financialservices.gov.in/pradhan-mantri-mudra-yojana-pmmy) | Loan categories, Tarun Plus restriction, collateral and eligible activities |
| `pmsby.json` | [DFS PMSBY](https://www.financialservices.gov.in/pmsby) | Entry/exit ages, premium, covered death/disability and exclusions |
| `pmuy.json` | [PMUY application guidance](https://www.pmuy.gov.in/ujjwala2.html) | Current allocation, eligibility, documents, connection benefit and charges |

For each record:

- Confirm the source is an official government or statutory-authority page and still live.
- Confirm the programme is accepting or serving beneficiaries now; do not infer activity
  from an old guideline alone.
- Compare every amount, age, date, category, exclusion, document, and step.
- Remove claims that are not supported by the linked source or add a newer official source.
- Keep state-specific benefits and rules out of a central record unless the state is named.
- Do not convert a discovery-only record into a deterministic rule set unless every branch
  of the decision can be represented and cited.

After review, validate without writing:

```powershell
janmitra-seed data --dry-run --confirm-reviewed --actor "Your Name"
```

Publish only after that command succeeds:

```powershell
janmitra-seed data --confirm-reviewed --actor "Your Name"
```
