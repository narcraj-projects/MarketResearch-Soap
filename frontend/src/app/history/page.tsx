import { HistoryScreen } from "@/components/history-screen";
export default async function Page({ searchParams }: { searchParams: Promise<{ before?: string; after?: string; before_version?: string; after_version?: string }> }) {
  const params = await searchParams;
  return <HistoryScreen key={`${params.before}:${params.after}:${params.before_version}:${params.after_version}`} initialBefore={params.before} initialAfter={params.after} initialBeforeVersion={params.before_version} initialAfterVersion={params.after_version}/>;
}
