import type { Metadata } from "next";
import { DataExportPage } from "@/components/data-export-page";

export const metadata: Metadata = { title: "Data export request | Clastio", description: "Download an account summary or ask Clastio support for wider data access.", robots: { index: false, follow: false } };

export default function Page() { return <DataExportPage />; }
