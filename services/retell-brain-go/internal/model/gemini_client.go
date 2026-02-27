package model

import _ "google.golang.org/genai"

const (
	VertexModelName = "gemini-3-flash-preview"
	ThinkingLevel   = "low"
)

// This package intentionally pins the SDK and model contract for the realtime brain.
// Concrete generation wiring is attached in deployment-specific adapters.
