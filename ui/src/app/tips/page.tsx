"use client";

import Link from "next/link";

export default function Tips() {
  const sections = [
    {
      title: "Before Taking a Photo",
      icon: "📷",
      description: "Set up the image properly so the wound is clear and easy to assess.",
      tips: [
        "Wash your hands before touching the wound area.",
        "Gently clean the wound if needed so the skin is visible.",
        "Use good lighting. Natural daylight usually works best.",
        "Avoid glare, flash reflection, or shiny moisture on the skin.",
        "Keep the background plain and distraction-free.",
        "Make sure only one wound is visible in the image.",
      ],
    },
    {
      title: "How to Frame the Image",
      icon: "🎯",
      description: "A consistent photo makes tracking healing much easier.",
      tips: [
        "Keep the wound centered in the frame.",
        "Stay about 1 foot away from the wound.",
        "Include some surrounding skin for context.",
        "Take the photo from directly above the wound when possible.",
        "Do not zoom in too much.",
        "Hold your device steady or rest your hand on a stable surface.",
      ],
    },
    {
      title: "Tracking Progress Over Time",
      icon: "📈",
      description: "Consistency matters more than getting one perfect photo.",
      tips: [
        "Try to take each photo in similar lighting.",
        "Use a similar angle and distance each time.",
        "Upload a new photo every 2 to 3 days unless told otherwise by a clinician.",
        "Take another photo sooner if the wound suddenly looks worse.",
        "Compare trends over time instead of relying on one image.",
      ],
    },
    {
      title: "Daily Care Basics",
      icon: "🩹",
      description: "Simple habits can help support healing between uploads.",
      tips: [
        "Keep the area clean and dry unless told otherwise by a clinician.",
        "Change dressings as instructed.",
        "Avoid picking at scabs or healing skin.",
        "Protect the wound from friction, pressure, and dirt.",
        "Watch for redness, swelling, drainage, odor, or worsening pain.",
      ],
    },
  ];

  const quickTips = [
    ["💧", "Clean gently and keep the area protected."],
    ["⏰", "Upload a new photo every 2 to 3 days."],
    ["📷", "Use consistent lighting and distance each time."],
    ["🧼", "Keep the wound clean and visible in the image."],
  ];

  const warningSigns = [
    "Rapidly increasing redness",
    "Pus or foul-smelling drainage",
    "Fever or chills",
    "Worsening pain or swelling",
    "Bleeding that does not stop",
  ];

  return (
    <div className="ws-container space-y-6 pb-8">
      <Link
        href="/dashboard"
        style={{
          display: "inline-block",
          color: "#2563eb",
          textDecoration: "none",
          fontWeight: 600,
          marginBottom: 12,
        }}
      >
        ← Back to Dashboard
      </Link>

      <div className="rounded-3xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm sm:p-8">
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center rounded-full bg-white px-3 py-1 text-sm font-semibold text-blue-700 shadow-sm">
            Wound photo and care guidance
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
            Tips & Guidance
          </h1>

          <p className="mt-3 text-base leading-7 text-slate-600 sm:text-[17px]">
            Use these tips to take clearer wound photos, track healing more
            consistently, and know when it may be time to get medical attention.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {quickTips.map(([icon, text]) => (
          <div key={text} className="ws-card rounded-2xl p-4">
            <div className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-blue-50 text-xl">
              {icon}
            </div>
            <p className="text-sm leading-6 text-slate-700 sm:text-base">
              {text}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {sections.map((section) => (
          <div key={section.title} className="ws-card rounded-2xl p-5 sm:p-6">
            <div className="mb-4 flex items-start gap-4">
              <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-blue-50 text-2xl">
                {section.icon}
              </div>

              <div>
                <h2 className="text-xl font-bold text-slate-900">
                  {section.title}
                </h2>
                <p className="mt-1 text-sm leading-6 text-slate-600 sm:text-base">
                  {section.description}
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {section.tips.map((tip) => (
                <div
                  key={tip}
                  className="flex items-start gap-3 rounded-xl bg-slate-50 px-4 py-3"
                >
                  <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-blue-500" />
                  <p className="text-sm leading-6 text-slate-700 sm:text-base">
                    {tip}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="ws-card rounded-2xl p-5 sm:p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-emerald-50 text-xl">
              ✅
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                Best Practices for More Accurate Results
              </h2>
              <p className="mt-1 text-sm leading-6 text-slate-600 sm:text-base">
                Small habits can make the app more useful and your progress
                easier to understand.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              "Take photos at similar times of day when possible.",
              "Keep the same general distance and angle each upload.",
              "Retake the photo if the image looks blurry or dark.",
              "Avoid covering the wound with fingers, gauze, or clothing in the photo.",
              "Use the same wound profile each time so progress stays organized.",
              "If something changes quickly, upload a new image rather than waiting.",
            ].map((item) => (
              <div
                key={item}
                className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 sm:text-base"
              >
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 sm:p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-white text-xl shadow-sm">
              ⚠️
            </div>
            <div>
              <h2 className="text-xl font-bold text-rose-900">
                Seek Medical Attention If You Notice
              </h2>
              <p className="mt-1 text-sm leading-6 text-rose-800 sm:text-base">
                This app is for support and tracking. It does not replace a
                medical professional.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {warningSigns.map((sign) => (
              <div
                key={sign}
                className="rounded-xl bg-white/80 px-4 py-3 text-sm font-medium leading-6 text-rose-900 sm:text-base"
              >
                {sign}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-600 shadow-sm sm:p-6 sm:text-base">
        <span className="font-semibold text-slate-800">Reminder:</span> wound
        photos and app guidance can help you monitor changes over time, but they
        are not a diagnosis. If a wound looks significantly worse, becomes more
        painful, or you are worried about infection, seek medical care.
      </div>
    </div>
  );
}