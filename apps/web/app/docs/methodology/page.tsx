import Link from "next/link";

export const metadata = {
  title: "Methodology — Follow the Money",
  description:
    "How Follow the Money detects and measures correlation between campaign donations and voting behaviour.",
};

export default function MethodologyPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Home
        </Link>

        <h1 className="mt-4 text-3xl font-bold text-gray-900">
          Methodology
        </h1>
        <p className="mt-2 text-gray-500">
          How we measure correlation between campaign donations and voting
          behaviour — and why correlation is not causation.
        </p>

        {/* Disclaimer banner */}
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-5 py-4">
          <p className="text-sm font-semibold text-amber-800">
            Important disclaimer
          </p>
          <p className="mt-1 text-sm text-amber-700">
            Every statistic on this platform describes <em>correlation only</em>.
            A change in voting alignment after a large donation does not prove
            that the donation caused the change. Legislators vote for many
            reasons — party leadership, constituent preferences, personal
            conviction, and many others. We surface patterns; we do not allege
            quid pro quo.
          </p>
        </div>

        {/* Data sources */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">Data Sources</h2>
          <ul className="mt-3 space-y-2 text-sm text-gray-600">
            <li>
              <strong>Campaign finance:</strong> FEC individual contributions and
              PAC filings, accessed via the{" "}
              <span className="font-mono text-xs">openFEC</span> REST API.
              Data is ingested nightly.
            </li>
            <li>
              <strong>Roll-call votes (House):</strong> Congress.gov API v3.
              Every floor vote cast by House members for the current and previous
              two congresses.
            </li>
            <li>
              <strong>Roll-call votes (Senate):</strong> Senate.gov XML feeds.
              Same date range as House data.
            </li>
            <li>
              <strong>Bill classification:</strong> Each bill title and subject
              headings are run through a keyword-based NLP classifier that maps
              bills to one of our industry categories (e.g.{" "}
              <em>Energy &amp; Natural Resources</em>,{" "}
              <em>Finance &amp; Banking</em>). The NLP confidence score is
              stored alongside each bill and shown in the voting record table.
            </li>
          </ul>
        </section>

        {/* Alignment score */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">
            Alignment Score
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            For a given <em>(representative, industry)</em> pair, the alignment
            score is:
          </p>
          <div className="mt-3 overflow-x-auto rounded-lg bg-gray-900 px-5 py-4 font-mono text-sm text-green-300">
            alignment = yes_votes / total_relevant_votes
          </div>
          <p className="mt-3 text-sm text-gray-600">
            A vote is <em>relevant</em> if the bill was tagged to the industry.
            A vote is <em>aligned</em> if the representative voted YES. NO,
            ABSTAIN, and NOT VOTING all count as non-aligned.
          </p>
          <p className="mt-2 text-sm text-gray-600">
            We compute two scores per industry — one for the 24-month window
            before the major donation event, and one for the 24-month window
            after — and report the shift:
          </p>
          <div className="mt-3 overflow-x-auto rounded-lg bg-gray-900 px-5 py-4 font-mono text-sm text-green-300">
            shift = after_score − before_score
          </div>
          <p className="mt-2 text-sm text-gray-600">
            A positive shift means the representative voted more favourably
            toward the industry after receiving the donation. A negative shift
            means the opposite.
          </p>
        </section>

        {/* Statistical thresholds */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">
            Statistical Thresholds
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            A correlation is only surfaced to users when <em>all three</em> of
            the following conditions are met:
          </p>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-gray-600">
            <li>
              <strong>Minimum sample size:</strong> at least 5 relevant votes in
              the combined before + after window (<code>evidence_count ≥ 5</code>
              ).
            </li>
            <li>
              <strong>Meaningful magnitude:</strong> the absolute shift is at
              least 15 percentage points (<code>|shift| ≥ 0.15</code>).
            </li>
            <li>
              <strong>Statistical significance:</strong> Fisher&rsquo;s exact
              test on the 2×2 contingency table produces{" "}
              <code>p&#8209;value&nbsp;&lt;&nbsp;0.05</code> (two-tailed).
            </li>
          </ol>
        </section>

        {/* Fisher's exact test */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">
            Fisher&rsquo;s Exact Test
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            We use Fisher&rsquo;s exact test (two-tailed) on the following 2×2
            contingency table:
          </p>
          <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="w-full text-center text-sm">
              <thead className="border-b border-gray-200 bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-2 text-left font-medium" />
                  <th className="px-4 py-2 font-medium">Voted YES</th>
                  <th className="px-4 py-2 font-medium">Did not vote YES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                <tr>
                  <td className="px-4 py-2 text-left font-medium text-gray-500">
                    Before donation
                  </td>
                  <td className="px-4 py-2">before_yes</td>
                  <td className="px-4 py-2">before_no</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 text-left font-medium text-gray-500">
                    After donation
                  </td>
                  <td className="px-4 py-2">after_yes</td>
                  <td className="px-4 py-2">after_no</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-gray-600">
            Fisher&rsquo;s exact test is appropriate here because the counts in
            each cell are often small. It tests the null hypothesis that the
            proportion of YES votes is the same before and after the donation
            event.
          </p>
        </section>

        {/* Confidence levels */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">
            Confidence Levels
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            All displayed correlations have already passed the three thresholds
            above. Within those, we assign a confidence level based on effect
            strength and sample size:
          </p>
          <ul className="mt-3 space-y-2 text-sm text-gray-600">
            <li>
              <span className="inline-block h-2 w-2 rounded-full bg-green-500 align-middle" />{" "}
              <strong>High</strong> — p&#8209;value &lt; 0.01 and evidence_count
              ≥ 20
            </li>
            <li>
              <span className="inline-block h-2 w-2 rounded-full bg-yellow-400 align-middle" />{" "}
              <strong>Medium</strong> — p&#8209;value &lt; 0.05 and evidence_count
              ≥ 10
            </li>
            <li>
              <span className="inline-block h-2 w-2 rounded-full bg-gray-300 align-middle" />{" "}
              <strong>Low</strong> — meets minimum thresholds but borderline
              sample size or p&#8209;value
            </li>
          </ul>
        </section>

        {/* Limitations */}
        <section className="mt-8">
          <h2 className="text-xl font-semibold text-gray-800">Limitations</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-gray-600">
            <li>
              <strong>Industry classification is approximate.</strong> Our NLP
              classifier uses keyword matching; it may mis-tag bills that touch
              multiple industries or use unusual language.
            </li>
            <li>
              <strong>Dark money is not tracked.</strong> Donations routed
              through 501(c)(4) organisations are not disclosed under current
              law and are therefore not included in this analysis.
            </li>
            <li>
              <strong>The analysis window is fixed at 24 months.</strong> Some
              policy areas have longer legislative cycles; a 24-month window may
              capture or miss relevant votes depending on timing.
            </li>
            <li>
              <strong>Small sample sizes reduce reliability.</strong> Even with
              our minimum evidence_count threshold, correlations based on 5–9
              votes should be treated with extra caution.
            </li>
            <li>
              <strong>Party-line voting inflates scores.</strong> If an entire
              party votes the same way on industry bills, individual correlation
              scores will be high even if the representative received no
              donations from that industry.
            </li>
          </ul>
        </section>

        <div className="mt-10 border-t border-gray-200 pt-6 text-xs text-gray-400">
          Data sourced from FEC and Congress.gov. All source code is open.
          Last methodology update: March 2026.
        </div>
      </div>
    </main>
  );
}
