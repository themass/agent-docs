import { webPageJsonLd } from "@/lib/seo/site";

type Props = {
  path: string;
  name: string;
  description: string;
};

export function PageJsonLd({ path, name, description }: Props) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(webPageJsonLd(path, name, description)),
      }}
    />
  );
}
