import { PublicInfoPage } from "@/components/public-info-page";
import { publicPages } from "@/lib/public-pages";
import { pageMetadata } from "@/lib/seo";
const page = publicPages[1];
export const metadata = pageMetadata(page.title, page.description, page.path);
export default function Page() { return <PublicInfoPage page={page} />; }
