# How it works

The first diagram places the check inside remediation, the second walks one finding through the tool's commands, and the third shows how the folders of this repository fit together. All three are Mermaid text inside this file, which GitHub renders on the page, so changing a diagram is an ordinary text edit. Every finding and figure named here comes from the two invented cases in [finding/cases](../finding/README.md).

## What remediation is, and where the check sits

```mermaid
flowchart TD
    subgraph work["The bank's work"]
        direction LR
        A["1. Finding<br/>The issuer writes<br/>up a weakness and<br/>a date for the fix"]
        B["2. Plan<br/>Milestones, owner<br/>roles and dates,<br/>which the board<br/>approves"]
        C["3. Work and evidence<br/>The bank makes<br/>the fix and files<br/>signed evidence"]
        D["4. Closure memo<br/>Cites a page for<br/>every figure, date<br/>and quotation"]
        A --> B --> C --> D
    end
    subgraph engine["RegRem Engine"]
        direction LR
        K["The check<br/>Reads the plan,<br/>evidence and memo.<br/>Looks for each claim<br/>on its cited page."]
        L["The list<br/>One row for each<br/>thing that did<br/>not check"]
        K --> L
    end
    subgraph closure["Sign-off and closure"]
        direction LR
        S["5. Sign-off<br/>Rows ruled on or<br/>fixed, the board's<br/>approval recorded,<br/>the owner signs"]
        T["6. Internal audit<br/>tests whether<br/>the fix works"]
        X["7. The issuer<br/>closes the finding<br/>or sends it back"]
        S --> T --> X
    end
    work --> engine --> closure
    classDef shade fill:#fde7d9,stroke:#9a3412,color:#1f1e1d
    class K,L shade
```

Remediation is the work a bank does to fix a weakness someone has written up, and to show with evidence that it did. The issuer is the Supervisor, the bank's internal audit, or for a weakness the bank found on its own, the bank's issue-management owner. The shaded check runs between the memo and the owner's signature, and it reads the plan and the evidence, so a milestone counts only while its evidence stays signed. Whether the fix works is for internal audit to test, and only the issuer can close the finding.

## One finding through the commands

```mermaid
flowchart TD
    subgraph setup["Set up the folder"]
        direction LR
        N["finding new<br/>../findings/ID makes<br/>the folder and<br/>its templates"]
        F["A person pastes<br/>the letter, fills<br/>plan.md and adds<br/>the evidence"]
        CV["finding covers<br/>drafts each cover.<br/>A person types<br/>Signed by and Status."]
        M["The closure memo<br/>is drafted, with<br/>a cite after<br/>every claim"]
        N --> F --> CV --> M
    end
    C["finding check<br/>prints the milestones,<br/>a board summary and<br/>the memo check. Exits 1<br/>while a person still<br/>has work to do."]
    E["finding eval<br/>plants errors in memory<br/>and lists each miss"]
    Q{"Anything holding<br/>back the signature?"}
    R["People act<br/>The owner rules on rows<br/>in rulings.md. Someone<br/>fixes the memo or the<br/>evidence. The board's<br/>approval goes into<br/>record.md."]
    S["finding sign<br/>At a terminal, the owner<br/>types the role and the<br/>fingerprint's first<br/>eight characters"]
    REC["record.md holds the<br/>signature, fingerprint<br/>and kit release. Any<br/>later edit to a file it<br/>covers needs a new<br/>signature."]
    setup --> C --> Q
    C -.->|when the memo is ready| E
    Q -->|yes| R --> C
    Q -->|no, so the check prints<br/>the folder's fingerprint| S --> REC
    classDef shade fill:#fde7d9,stroke:#9a3412,color:#1f1e1d
    class N,CV,C,E,S shade
```

Each shaded box is a command, run from the folder that holds finding/, where `finding` is short for `finding/finding`, and on Windows you type `py -I finding\finding.py` in its place. On the invented case MRA-CMP-07, checked as of 2026-11-04, the first row is a memo figure of 1,248 where the cited page says 1,284. A ruling is one line in closure/rulings.md, and the check prints each cleared row with its reason, so clearing that figure would stay in plain sight. On the other invented case, IA-CMP-02, nothing holds the signature back, so the check prints the fingerprint a381fa0f, and `sign` refuses piped input because it runs only at a terminal.

## How the pieces fit

```mermaid
flowchart TD
    P["The team<br/>the finding owner, other<br/>bank roles and whoever<br/>the bank brings in"]
    AS["assistant/<br/>a written procedure<br/>for each drafting job,<br/>for any AI assistant<br/>the bank allows"]
    FD["The finding folder<br/>finding.md, plan.md,<br/>evidence/ with covers,<br/>closure/memo.md,<br/>rulings.md, record.md"]
    subgraph check["The check, no AI model"]
        FT["finding/finding.py<br/>new, covers, check,<br/>eval, sign, size,<br/>--version"]
        DR["finding/documents.py<br/>reads PDF text layers,<br/>Word, Excel, CSV,<br/>saved email, text"]
        EN["tieout/<br/>five engine files tie<br/>each claim to its page"]
        FT --> DR --> EN
        FT --> EN
    end
    LIB["library/<br/>21 invented cases,<br/>one per kind of miss"]
    PR["tieout/providers.py<br/>optional model step,<br/>off by default"]
    OUT["The screen<br/>milestone states, a board<br/>summary and the list,<br/>for the team to act on"]
    AS -.->|drafts into| FD
    P -->|types Signed by lines,<br/>rules on rows,<br/>records approvals| FD
    FD --> FT
    LIB -->|eval --library| FT
    PR -.-x|never imported| check
    check --> OUT
    EN ~~~ OUT
    classDef shade fill:#fde7d9,stroke:#9a3412,color:#1f1e1d
    class FT,DR,EN shade
```

The procedures in [assistant/](../assistant/README.md) tell whatever AI assistant the bank allows to draft into the folder and never to write the rulings or the record, or to sign. The finding tool reads the folder through its document reader and five files from [tieout/](../tieout/README.md). No AI model sits on that path, so one folder checked as of one date always gives the same page. The engine's optional model step lives in tieout/providers.py, off by default, and the finding tool never imports it. Each release has to pass all 21 invented cases in [library/](../library/README.md), and the six marked as a known limit keep a written record of what the check cannot see.

## Limits

The check looks for each claim only on the page its cite names, and it never sets two documents side by side. So a wrong figure ties whenever the cited page holds that same figure somewhere, and a person reads every sentence against its page. Every case in this repository is invented, and no bank has run the tool on a real finding. The [walk in finding/DEMO.md](../finding/DEMO.md) runs every command shown here, and [finding/README.md](../finding/README.md) sets out each rule the check applies.
