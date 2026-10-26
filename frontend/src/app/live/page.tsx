import { LiveScreen } from "@/components/live-screen";
export default async function Page({ searchParams }: { searchParams: Promise<{ run?: string }> }) { const { run } = await searchParams; return <LiveScreen key={run || "latest"} runId={run}/>; }
