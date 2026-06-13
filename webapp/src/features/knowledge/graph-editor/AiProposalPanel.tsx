import { Sparkles } from "lucide-react";

import type { KnowledgeAiProposal } from "../api";

type AiProposalPanelProps = {
  isLoading: boolean;
  onReview: (proposalId: string, action: "approve" | "reject") => void;
  proposals: KnowledgeAiProposal[];
  reviewing: boolean;
};

export function AiProposalPanel({ isLoading, onReview, proposals, reviewing }: AiProposalPanelProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-brand-700" />
        <h3 className="text-sm font-semibold text-slate-950">Предложения AI</h3>
      </div>
      <p className="mt-1 text-xs leading-5 text-slate-500">Предложения не меняют граф без ревью.</p>
      <div className="mt-3 space-y-3">
        {isLoading ? <p className="text-sm text-slate-500">Загрузка предложений...</p> : null}
        {!isLoading && proposals.length === 0 ? <p className="text-sm text-slate-500">Ожидающих предложений нет.</p> : null}
        {proposals.slice(0, 3).map((proposal) => (
          <article className="rounded-lg border border-slate-200 bg-slate-50 p-3" key={proposal.proposal_id}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-950">{proposal.title}</p>
                <p className="mt-1 text-xs text-slate-500">Уверенность: {proposal.confidence_score ?? "не указана"}</p>
              </div>
              <span className="rounded-pill bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">Ревью</span>
            </div>
            {proposal.rationale ? <p className="mt-2 text-xs leading-5 text-slate-600">{proposal.rationale}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                className="rounded-pill bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                disabled={reviewing}
                onClick={() => onReview(proposal.proposal_id, "approve")}
                type="button"
              >
                Одобрить предложение
              </button>
              <button
                className="rounded-pill border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-60"
                disabled={reviewing}
                onClick={() => onReview(proposal.proposal_id, "reject")}
                type="button"
              >
                Отклонить
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
