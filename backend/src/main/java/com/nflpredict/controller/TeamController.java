package com.nflpredict.controller;

import com.nflpredict.model.Team;
import com.nflpredict.repository.TeamRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/teams")
@CrossOrigin(origins = "*") // Allow requests from React Native app
public class TeamController {

    @Autowired
    private TeamRepository teamRepository;

    // Get all teams
    @GetMapping
    public List<Team> getAllTeams() {
        return teamRepository.findAll();
    }

    // Get team by ID
    @GetMapping("/{id}")
    public ResponseEntity<Team> getTeamById(@PathVariable Long id) {
        return teamRepository.findById(id)
                .map(team -> ResponseEntity.ok().body(team))
                .orElse(ResponseEntity.notFound().build());
    }

    // Get team by abbreviation
    @GetMapping("/abbr/{abbreviation}")
    public ResponseEntity<Team> getTeamByAbbreviation(@PathVariable String abbreviation) {
        return teamRepository.findByAbbreviation(abbreviation.toUpperCase())
                .map(team -> ResponseEntity.ok().body(team))
                .orElse(ResponseEntity.notFound().build());
    }

    // Get teams by conference
    @GetMapping("/conference/{conference}")
    public List<Team> getTeamsByConference(@PathVariable String conference) {
        return teamRepository.findByConference(conference.toUpperCase());
    }

    // Get teams by division
    @GetMapping("/conference/{conference}/division/{division}")
    public List<Team> getTeamsByDivision(
            @PathVariable String conference,
            @PathVariable String division) {
        return teamRepository.findByConferenceAndDivision(
                conference.toUpperCase(),
                division.substring(0, 1).toUpperCase() + division.substring(1).toLowerCase());
    }

    // Search teams
    @GetMapping("/search")
    public List<Team> searchTeams(@RequestParam String q) {
        return teamRepository.findBySearch(q);
    }
}