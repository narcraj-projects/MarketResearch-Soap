import { NextRequest } from 'next/server';
import { proxy } from '@/lib/proxy';
export async function GET(request: NextRequest) { return proxy(request, '/api/live-pilot'); }
