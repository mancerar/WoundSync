import { Suspense } from "react";
import CaptureClient from "./CaptureClient";

export default function Page() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <CaptureClient />
    </Suspense>
  );
}
