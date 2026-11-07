import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm font-semibold text-ink-500">404</p>
      <h1 className="text-xl font-semibold text-ink-900">这个页面不存在</h1>
      <p className="text-sm text-ink-500">地址可能写错了，或者页面已经移走。</p>
      <Link href="/" className="btn btn-sm btn-primary mt-2">
        回到首页
      </Link>
    </div>
  );
}
