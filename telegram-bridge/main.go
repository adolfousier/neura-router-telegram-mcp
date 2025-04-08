package main

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/gotd/td/session"
	"github.com/gotd/td/telegram"
	"github.com/gotd/td/telegram/auth"
	"github.com/gotd/td/tg"
	"gopkg.in/ini.v1"
)

// noSignUp can be embedded to prevent signing up.
type noSignUp struct{}

func (c noSignUp) SignUp(ctx context.Context) (auth.UserInfo, error) {
	return auth.UserInfo{}, fmt.Errorf("signing up is not supported")
}

func (c noSignUp) AcceptTermsOfService(ctx context.Context, tos tg.HelpTermsOfService) error {
	return &auth.SignUpRequired{TermsOfService: tos}
}

// termAuth implements authentication via terminal.
type termAuth struct {
	noSignUp
	phone string
}

func (a termAuth) Phone(_ context.Context) (string, error) {
	return a.phone, nil
}

func (a termAuth) Password(_ context.Context) (string, error) {
	fmt.Print("Enter 2FA password: ")
	bytePwd, err := bufio.NewReader(os.Stdin).ReadBytes('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(bytePwd)), nil
}

func (a termAuth) Code(_ context.Context, _ *tg.AuthSentCode) (string, error) {
	fmt.Print("Enter code: ")
	byteCode, err := bufio.NewReader(os.Stdin).ReadBytes('\n')
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(byteCode)), nil
}

func main() {
	log.Println("Starting Telegram bridge...")

	// Load configuration
	cfg, err := ini.Load("telegram-bridge/config.ini") // Ensure path is correct relative to CWD
	if err != nil {
		log.Fatalf("Failed to load config: %v\n", err)
	}

	apiIDStr := cfg.Section("telegram").Key("api_id").String()
	apiHash := cfg.Section("telegram").Key("api_hash").String()
	phoneNumber := cfg.Section("telegram").Key("phone_number").String()

	var apiID int
	_, err = fmt.Sscan(apiIDStr, &apiID)
	if err != nil {
		log.Fatalf("Invalid api_id: %v\n", err)
	}

	if apiHash == "" || phoneNumber == "" || apiID == 0 {
		log.Fatalf("api_id, api_hash, and phone_number must be set in config.ini")
	}

	// Set up session storage
	sessionDir := "telegram-bridge/store" // Relative to CWD
	if err := os.MkdirAll(sessionDir, 0700); err != nil {
		log.Fatalf("Failed to create session directory: %v", err)
	}
	sessionStorage := &session.FileStorage{
		Path: fmt.Sprintf("%s/telegram.session", sessionDir),
	}

	// Create Telegram client
	client := telegram.NewClient(apiID, apiHash, telegram.Options{
		SessionStorage: sessionStorage,
		// You might need to add other options like log levels, etc.
	})

	// Run the client
	err = client.Run(context.Background(), func(ctx context.Context) error {
		log.Println("Client started, checking authentication...")

		// Check authentication status
		status, err := client.Auth().Status(ctx)
		if err != nil {
			return fmt.Errorf("failed to get auth status: %w", err)
		}

		// Authenticate if necessary
		if !status.Authorized {
			log.Println("Not authorized, performing authentication...")
			flow := auth.NewFlow(termAuth{phone: phoneNumber}, auth.SendCodeOptions{})
			if err := client.Auth().IfNecessary(ctx, flow); err != nil {
				return fmt.Errorf("authentication failed: %w", err)
			}
			log.Println("Authentication successful!")
		} else {
			log.Println("Already authorized.")
		}

		// Get self info
		self, err := client.Self(ctx)
		if err != nil {
			return fmt.Errorf("failed to get self info: %w", err)
		}
		log.Printf("Logged in as: %s %s (@%s)\n", self.FirstName, self.LastName, self.Username)

		// Placeholder for message handling or other logic
		log.Println("Telegram bridge running. Press Ctrl+C to exit.")
		<-ctx.Done() // Keep running until context is cancelled (e.g., Ctrl+C)
		return ctx.Err()
	})

	if err != nil {
		log.Fatalf("Telegram client run failed: %v", err)
	}

	log.Println("Telegram bridge stopped.")
}
