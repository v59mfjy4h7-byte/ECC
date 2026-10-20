#!/bin/bash
# Dubbelklicka för att starta Klar AI Forex Lab (kräver att Docker Desktop är igång).
cd "$(dirname "$0")" || exit 1
if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop verkar inte vara igång. Starta det, vänta på 'Engine running' och försök igen."
  read -r -p "Tryck Enter för att stänga."
  exit 1
fi
echo "Bygger och startar (första gången tar det några minuter)..."
if ! docker compose up -d --build; then
  echo
  echo "Något gick fel. Kopiera texten ovan och skicka den till Claude."
  read -r -p "Tryck Enter för att stänga."
  exit 1
fi
echo "Klart! Öppnar http://localhost:8080"
open http://localhost:8080
