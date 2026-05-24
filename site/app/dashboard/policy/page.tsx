import { cpFetch } from "@/lib/cp-fetch";
import { PolicyRuleForm } from "@/components/dashboard/PolicyRuleForm";
import { PolicyRulesList } from "@/components/dashboard/PolicyRulesList";

export type PolicyRule = {
  id: string;
  name: string;
  enabled: boolean;
  priority: number;
  conditions: { field: string; op: string; value: string | number }[];
  action: "allow" | "block" | "notify";
  created_at: string;
  updated_at: string;
};

export default async function PolicyPage() {
  const rules = (await cpFetch<PolicyRule[]>("/v1/policy")) ?? [];

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold tracking-tight">Policy</h1>
      <p className="mt-1 max-w-2xl text-sm text-neutral-400">
        Rules are evaluated by ascending priority. The first matching rule wins;
        if none match, the default is <span className="font-mono">allow</span>.
      </p>

      <section className="mt-8">
        <h2 className="text-xs uppercase tracking-wider text-neutral-500">New rule</h2>
        <PolicyRuleForm />
      </section>

      <section className="mt-10">
        <h2 className="text-xs uppercase tracking-wider text-neutral-500">
          Rules ({rules.length})
        </h2>
        <PolicyRulesList rules={rules} />
      </section>
    </div>
  );
}
