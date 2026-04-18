export function CodeSample() {
  return (
    <pre className="code-block">
      <code>
        <span className="k">from</span> self_heal <span className="k">import</span> repair{"\n\n"}

        <span className="k">def</span> <span className="f">test_dollar_comma</span>(fn):{"\n"}
        {"    "}<span className="k">assert</span> fn(<span className="s">&quot;$1,299&quot;</span>) == <span className="s">1299.0</span>{"\n\n"}

        <span className="k">def</span> <span className="f">test_rupee</span>(fn):{"\n"}
        {"    "}<span className="k">assert</span> fn(<span className="s">&quot;Rs 500&quot;</span>) == <span className="s">500.0</span>{"\n\n"}

        <span className="d">@repair</span>(tests=[test_dollar_comma, test_rupee]){"\n"}
        <span className="k">def</span> <span className="f">extract_price</span>(text: <span className="k">str</span>) -&gt; <span className="k">float</span>:{"\n"}
        {"    "}<span className="c"># Naive: only handles &quot;$X.YY&quot;</span>{"\n"}
        {"    "}<span className="k">return</span> <span className="k">float</span>(text.replace(<span className="s">&quot;$&quot;</span>, <span className="s">&quot;&quot;</span>)){"\n\n"}

        <span className="c"># Triggers the repair loop until ALL tests pass.</span>{"\n"}
        extract_price(<span className="s">&quot;Rs 500&quot;</span>){"\n"}
      </code>
    </pre>
  );
}
