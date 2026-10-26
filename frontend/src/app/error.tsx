"use client";
export default function ErrorPage({ reset }: { reset: () => void }) { return <main id="main" className="container state-panel"><h1>Something interrupted this page.</h1><p role="alert">Please try again. No business action has been approved.</p><button className="button primary" onClick={reset}>Try again</button></main>; }
