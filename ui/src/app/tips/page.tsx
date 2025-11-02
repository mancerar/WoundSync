export default function Tips() {
  const tips = [
    ["💧", "Clean the wound gently and keep the area dry."],
    ["⏰", "Upload a new photo every 2–3 days to track healing."],
    ["📷", "Use consistent lighting and distance for each image."],
    ["📏", "Include a small ruler or marker to show wound size."]
  ];

  return (
    <div className="ws-container space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
          Tips & Guidance
        </h1>
        <p className="mt-1 text-slate-600 text-base sm:text-[17px]">
          Keep steady habits for clear progress
        </p>
      </div>

      {/* Tip Cards */}
      <div className="space-y-3">
        {tips.map(([icon, text]) => (
          <div
            key={text}
            className="flex items-center gap-3 ws-card p-4 text-slate-800"
          >
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue-50 text-xl">
              {icon}
            </div>
            <p className="text-base">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}