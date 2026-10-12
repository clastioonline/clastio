import { SupportInfoPage } from "@/components/support-info-page";
import { supportPages } from "@/lib/support-pages";
import { pageMetadata } from "@/lib/seo";
const page = supportPages.find(item => item.path === "/data-privacy")!;
export const metadata = pageMetadata(page.title, page.description, page.path);
export default function Page() { return <SupportInfoPage page={page} />; }
