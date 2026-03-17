# copy .pgn files created in the last 2 hours to afterGamesReport
find . -name "*.pgn" -type f -mmin -120 -not -path "./afterGamesReport/*" -exec cp {} ./afterGamesReport \;
