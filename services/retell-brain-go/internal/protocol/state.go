package protocol

import "time"

type State struct {
	AutoReconnect         bool
	CurrentResponseID     string
	GenerationActive      bool
	OutboundStreamingOpen bool
	LastPingPongAt        time.Time
}

type Decision struct {
	SendPingPong        bool
	StopOutboundStream  bool
	CancelGeneration    bool
	DiscardPending      bool
	StartNewGeneration  bool
}

func (s *State) HandleInteraction(interactionType string, responseID string, now time.Time) Decision {
	decision := Decision{}
	switch interactionType {
	case "ping_pong":
		if s.AutoReconnect {
			decision.SendPingPong = true
		}
		s.LastPingPongAt = now
		return decision
	case "update_only":
		if s.GenerationActive {
			decision.StopOutboundStream = true
			s.OutboundStreamingOpen = false
		}
		return decision
	case "response_required", "reminder_required":
		if s.GenerationActive && responseID != "" && responseID != s.CurrentResponseID {
			decision.CancelGeneration = true
			decision.DiscardPending = true
		}
		s.CurrentResponseID = responseID
		s.GenerationActive = true
		s.OutboundStreamingOpen = true
		decision.StartNewGeneration = true
		return decision
	default:
		return decision
	}
}

func (s *State) HeartbeatStale(now time.Time) bool {
	if !s.AutoReconnect {
		return false
	}
	if s.LastPingPongAt.IsZero() {
		return true
	}
	return now.Sub(s.LastPingPongAt) > 5*time.Second
}
