import { ReportScreen } from "@/components/report-screen";
export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string; version?: string }> }) { const { run, version } = await searchParams; return <ReportScreen key={`${run || "latest"}:${version || "saved"}`} runId={run} reportVersion={version}/>; }
