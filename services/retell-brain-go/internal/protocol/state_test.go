package protocol

import (
	"testing"
	"time"
)

func TestPingPongAndStaleWindow(t *testing.T) {
	now := time.Now().UTC()
	s := &State{AutoReconnect: true}
	d := s.HandleInteraction("ping_pong", "", now)
	if !d.SendPingPong {
		t.Fatalf("expected send ping pong")
	}
	if s.HeartbeatStale(now.Add(4 * time.Second)) {
		t.Fatalf("heartbeat should not be stale at 4s")
	}
	if !s.HeartbeatStale(now.Add(6 * time.Second)) {
		t.Fatalf("heartbeat should be stale at 6s")
	}
}

func TestPreemptionRules(t *testing.T) {
	now := time.Now().UTC()
	s := &State{AutoReconnect: true, GenerationActive: true, CurrentResponseID: "resp-a", OutboundStreamingOpen: true}

	update := s.HandleInteraction("update_only", "", now)
	if !update.StopOutboundStream {
		t.Fatalf("update_only must stop outbound stream")
	}
	if update.CancelGeneration || update.DiscardPending {
		t.Fatalf("update_only must not cancel or discard")
	}
	if !s.GenerationActive {
		t.Fatalf("generation should remain active after update_only")
	}

	next := s.HandleInteraction("response_required", "resp-b", now.Add(10*time.Millisecond))
	if !next.CancelGeneration || !next.DiscardPending {
		t.Fatalf("new response id must cancel and discard previous generation")
	}
	if s.CurrentResponseID != "resp-b" {
		t.Fatalf("response id not updated")
	}
}
