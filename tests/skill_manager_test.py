# -*- coding: utf-8 -*-
"""Test AgentSkillManager with focus on core functionality."""
# pylint: disable=protected-access
import os
import tempfile
import shutil
import time
from unittest import TestCase

from agentscope.tool._skill_manager import AgentSkillManager


class SkillManagerBasicTest(TestCase):
    """Test basic functionality.

    Monitoring, registration, removal, and error handling.
    """

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = AgentSkillManager(
            agent_skill_instruction="Test instruction: {skills}",
            agent_skill_template="Skill: {name} - {description} ({dir})",
        )

    def tearDown(self) -> None:
        """Clean up test environment after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_skill_dir(self, name: str, description: str) -> str:
        """Helper to create a valid skill directory with SKILL.md."""
        skill_dir = os.path.join(self.test_dir, name)
        os.makedirs(skill_dir, exist_ok=True)

        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"name: {name}\n")
            f.write(f"description: {description}\n")
            f.write("---\n")
            f.write("\n# Skill Content\n")

        return skill_dir

    # Directory Monitoring Tests
    def test_monitor_valid_directory_with_path_normalization(
        self,
    ) -> None:
        """Test monitoring a valid directory and path normalization."""
        # Test with relative path
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)
        relative_path = os.path.join(subdir, "..")

        self.manager.monitor_agent_skills(relative_path)

        abs_path = os.path.abspath(os.path.normpath(relative_path))
        self.assertIn(abs_path, self.manager.monitored_dirs)
        self.assertEqual(abs_path, os.path.abspath(self.test_dir))

    def test_monitor_invalid_directory_raises_error(self) -> None:
        """Test monitoring invalid directory or file raises ValueError."""
        # Test nonexistent directory
        invalid_dir = os.path.join(self.test_dir, "nonexistent")
        with self.assertRaises(ValueError) as context:
            self.manager.monitor_agent_skills(invalid_dir)
        self.assertIn("Invalid directory", str(context.exception))

        # Test file instead of directory
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        with self.assertRaises(ValueError) as context:
            self.manager.monitor_agent_skills(test_file)
        self.assertIn("Invalid directory", str(context.exception))

    def test_monitor_multiple_directories(self) -> None:
        """Test monitoring multiple directories."""
        dir1 = os.path.join(self.test_dir, "dir1")
        dir2 = os.path.join(self.test_dir, "dir2")
        os.makedirs(dir1)
        os.makedirs(dir2)

        self.manager.monitor_agent_skills(dir1)
        self.manager.monitor_agent_skills(dir2)

        self.assertEqual(len(self.manager.monitored_dirs), 2)
        self.assertIn(os.path.abspath(dir1), self.manager.monitored_dirs)
        self.assertIn(os.path.abspath(dir2), self.manager.monitored_dirs)

    def test_remove_monitored_directory_with_skills(self) -> None:
        """Test removing monitored directory removes its skills.

        Preserves manual skills.
        """
        # Add a manual skill
        manual_skill_dir = self._create_skill_dir(
            "manual_skill",
            "Manual skill",
        )
        self.manager.register_agent_skill(manual_skill_dir)

        # Add a monitored skill
        monitored_dir = os.path.join(self.test_dir, "monitored")
        os.makedirs(monitored_dir)
        monitored_skill_dir = os.path.join(monitored_dir, "monitored_skill")
        os.makedirs(monitored_skill_dir)
        skill_md_path = os.path.join(monitored_skill_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(
                "---\nname: monitored_skill\n"
                "description: Monitored skill\n---\n",
            )

        self.manager._monitored_dirs.add(os.path.abspath(monitored_dir))
        self.manager._skills["monitored_skill"] = {
            "name": "monitored_skill",
            "description": "Monitored skill",
            "dir": monitored_skill_dir,
            "source": "monitored",
            "monitored_root": os.path.abspath(monitored_dir),
        }

        # Remove the monitored directory
        self.manager.remove_monitored_directory(monitored_dir)

        # Verify manual skill preserved, monitored skill removed
        self.assertIn("manual_skill", self.manager.skills)
        self.assertNotIn("monitored_skill", self.manager.skills)
        self.assertNotIn(
            os.path.abspath(monitored_dir),
            self.manager.monitored_dirs,
        )

    # Manual Registration Tests
    def test_register_valid_skill(self) -> None:
        """Test registering a valid skill with path normalization."""
        skill_dir = self._create_skill_dir("test_skill", "A test skill")

        # Register with relative path
        relative_path = os.path.join(skill_dir, "..", "test_skill")
        self.manager.register_agent_skill(relative_path)

        # Verify skill is registered with normalized path
        self.assertIn("test_skill", self.manager.skills)
        skill = self.manager.skills["test_skill"]
        self.assertEqual(skill["name"], "test_skill")
        self.assertEqual(skill["description"], "A test skill")
        self.assertEqual(skill["dir"], os.path.abspath(skill_dir))
        self.assertEqual(skill["source"], "manual")
        self.assertIsNone(skill["monitored_root"])

    def test_register_invalid_skill_raises_error(self) -> None:
        """Test registering invalid skills raises ValueError."""
        # Nonexistent directory
        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(
                os.path.join(self.test_dir, "nonexistent"),
            )
        self.assertIn("does not exist", str(context.exception))

        # File instead of directory
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test")
        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(test_file)
        self.assertIn("not a directory", str(context.exception))

        # Missing SKILL.md
        skill_dir = os.path.join(self.test_dir, "no_skill_md")
        os.makedirs(skill_dir)
        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(skill_dir)
        self.assertIn("SKILL.md", str(context.exception))

    def test_register_skill_missing_required_fields(self) -> None:
        """Test registering skill with missing required fields.

        Raises ValueError.
        """
        # Missing name field
        skill_dir = os.path.join(self.test_dir, "missing_name")
        os.makedirs(skill_dir)
        with open(
            os.path.join(skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("---\ndescription: A test skill\n---\n")
        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(skill_dir)
        self.assertIn("name", str(context.exception).lower())

        # Empty name field
        skill_dir2 = os.path.join(self.test_dir, "empty_name")
        os.makedirs(skill_dir2)
        with open(
            os.path.join(skill_dir2, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("---\nname: \ndescription: A test skill\n---\n")
        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(skill_dir2)
        self.assertIn("name", str(context.exception).lower())

    def test_register_duplicate_skill_name_raises_error(self) -> None:
        """Test registering skill with duplicate name.

        Raises ValueError.
        """
        skill_dir1 = self._create_skill_dir("duplicate_skill", "First skill")
        self.manager.register_agent_skill(skill_dir1)

        # Create second skill with same name
        skill_dir2 = os.path.join(self.test_dir, "duplicate_skill_2")
        os.makedirs(skill_dir2)
        with open(
            os.path.join(skill_dir2, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: duplicate_skill\ndescription: Second skill\n---\n",
            )

        with self.assertRaises(ValueError) as context:
            self.manager.register_agent_skill(skill_dir2)
        self.assertIn("already registered", str(context.exception))

    # Property Tests
    def test_properties_are_readonly(self) -> None:
        """Test that monitored_dirs and skills properties return.

        Immutable views.
        """
        self.manager.monitor_agent_skills(self.test_dir)
        self._create_skill_dir("test_skill", "Test")
        self.manager.get_agent_skill_prompt()

        # Test monitored_dirs is frozenset
        monitored = self.manager.monitored_dirs
        self.assertIsInstance(monitored, frozenset)
        with self.assertRaises(AttributeError):
            monitored.add("test")  # type: ignore

        # Test skills is immutable
        skills = self.manager.skills
        with self.assertRaises(TypeError):
            skills["new_skill"] = {}  # type: ignore


class SkillManagerLazyLoadingTest(TestCase):
    """Test lazy loading and caching mechanisms."""

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = AgentSkillManager(
            agent_skill_instruction="Test instruction: {skills}",
            agent_skill_template="Skill: {name} - {description} ({dir})",
        )

    def tearDown(self) -> None:
        """Clean up test environment after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_skill_dir(self, name: str, description: str) -> str:
        """Helper to create a valid skill directory with SKILL.md."""
        skill_dir = os.path.join(self.test_dir, name)
        os.makedirs(skill_dir, exist_ok=True)

        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"name: {name}\n")
            f.write(f"description: {description}\n")
            f.write("---\n")

        return skill_dir

    def test_monitor_does_not_scan_immediately(self) -> None:
        """Test that monitoring does not scan immediately (lazy loading)."""
        self._create_skill_dir("test_skill", "A test skill")

        self.manager.monitor_agent_skills(self.test_dir)

        # Verify no skills discovered yet
        self.assertEqual(len(self.manager.skills), 0)
        self.assertIn(
            os.path.abspath(self.test_dir),
            self.manager.monitored_dirs,
        )

    def test_get_prompt_triggers_lazy_loading(self) -> None:
        """Test that get_agent_skill_prompt triggers lazy loading.

        Discovers skills.
        """
        # Create multiple skills including nested
        self._create_skill_dir("skill1", "First skill")
        self._create_skill_dir("skill2", "Second skill")

        nested_dir = os.path.join(self.test_dir, "level1", "level2")
        os.makedirs(nested_dir, exist_ok=True)
        nested_skill_dir = os.path.join(nested_dir, "nested_skill")
        os.makedirs(nested_skill_dir)
        with open(
            os.path.join(nested_skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: nested_skill\ndescription: A nested skill\n---\n",
            )

        self.manager.monitor_agent_skills(self.test_dir)
        self.assertEqual(len(self.manager.skills), 0)

        # Trigger lazy loading
        prompt = self.manager.get_agent_skill_prompt()

        # Verify all skills discovered
        self.assertEqual(len(self.manager.skills), 3)
        self.assertIn("skill1", self.manager.skills)
        self.assertIn("skill2", self.manager.skills)
        self.assertIn("nested_skill", self.manager.skills)
        self.assertIn("skill1", prompt)
        self.assertIn("nested_skill", prompt)

    def test_lazy_loading_skips_invalid_skills(self) -> None:
        """Test that lazy loading gracefully skips invalid skills."""
        self._create_skill_dir("valid_skill", "A valid skill")

        # Create invalid skill (missing description)
        invalid_dir = os.path.join(self.test_dir, "invalid_skill")
        os.makedirs(invalid_dir)
        with open(
            os.path.join(invalid_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("---\nname: invalid_skill\n---\n")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()

        # Verify only valid skill discovered
        self.assertEqual(len(self.manager.skills), 1)
        self.assertIn("valid_skill", self.manager.skills)
        self.assertNotIn("invalid_skill", self.manager.skills)

    def test_lazy_loading_handles_name_conflicts(self) -> None:
        """Test that lazy loading handles name conflicts.

        First-wins strategy.
        """
        # Manually register a skill
        manual_skill_dir = self._create_skill_dir(
            "conflict_skill",
            "Manual skill",
        )
        self.manager.register_agent_skill(manual_skill_dir)

        # Create monitored skill with same name
        conflict_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(conflict_dir)
        conflict_skill_dir = os.path.join(conflict_dir, "conflict_skill_2")
        os.makedirs(conflict_skill_dir)
        with open(
            os.path.join(conflict_skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: conflict_skill\n"
                "description: Monitored skill\n---\n",
            )

        self.manager.monitor_agent_skills(conflict_dir)
        self.manager.get_agent_skill_prompt()

        # Verify manual skill kept (first-wins)
        self.assertEqual(len(self.manager.skills), 1)
        skill = self.manager.skills["conflict_skill"]
        self.assertEqual(skill["source"], "manual")
        self.assertEqual(skill["description"], "Manual skill")

    def test_lazy_loading_returns_none_when_no_skills(self) -> None:
        """Test that get_agent_skill_prompt returns None.

        When no skills exist.
        """
        self.manager.monitor_agent_skills(self.test_dir)
        prompt = self.manager.get_agent_skill_prompt()
        self.assertIsNone(prompt)

    def test_lazy_loading_includes_manual_and_monitored_skills(
        self,
    ) -> None:
        """Test that prompt includes both manual and monitored skills."""
        # Manual skill
        manual_skill_dir = self._create_skill_dir(
            "manual_skill",
            "Manual skill",
        )
        self.manager.register_agent_skill(manual_skill_dir)

        # Monitored skill
        monitored_dir = os.path.join(self.test_dir, "monitored")
        os.makedirs(monitored_dir)
        monitored_skill_dir = os.path.join(monitored_dir, "monitored_skill")
        os.makedirs(monitored_skill_dir)
        with open(
            os.path.join(monitored_skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: monitored_skill\n"
                "description: Monitored skill\n---\n",
            )

        self.manager.monitor_agent_skills(monitored_dir)
        prompt = self.manager.get_agent_skill_prompt()

        # Verify both in prompt
        self.assertEqual(len(self.manager.skills), 2)
        self.assertIn("manual_skill", prompt)
        self.assertIn("monitored_skill", prompt)

    # Caching Tests
    def test_cache_fast_path_when_unchanged(self) -> None:
        """Test that cache uses fast path when nothing changed."""
        self._create_skill_dir("test_skill", "A test skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()

        # Save cache state
        cache_before = dict(self.manager._skill_dir_mtime_cache)

        # Second scan without changes
        self.manager.get_agent_skill_prompt()

        # Verify cache unchanged (fast path used)
        self.assertEqual(cache_before, self.manager._skill_dir_mtime_cache)
        self.assertIn("test_skill", self.manager.skills)

    def test_cache_slow_path_when_directory_changed(self) -> None:
        """Test that cache detects directory changes.

        Triggers slow path.
        """
        self._create_skill_dir("skill1", "First skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 1)

        # Add new skill (changes directory mtime)
        time.sleep(0.01)
        self._create_skill_dir("skill2", "Second skill")

        # Second scan should detect change
        self.manager.get_agent_skill_prompt()

        # Verify new skill discovered
        self.assertEqual(len(self.manager.skills), 2)
        self.assertIn("skill1", self.manager.skills)
        self.assertIn("skill2", self.manager.skills)

    def test_force_refresh_clears_cache(self) -> None:
        """Test that refresh with force=True clears caches.

        Repopulates caches.
        """
        self._create_skill_dir("test_skill", "A test skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()

        # Verify caches populated
        self.assertGreater(len(self.manager._skill_dir_mtime_cache), 0)
        self.assertGreater(len(self.manager._monitored_dir_last_scan_mtime), 0)

        # Force refresh
        stats = self.manager.refresh_monitored_skills(force=True)

        # Verify caches repopulated and stats returned
        self.assertGreater(len(self.manager._skill_dir_mtime_cache), 0)
        self.assertIn("added", stats)
        self.assertIn("modified", stats)
        self.assertIn("removed", stats)

    def test_cache_cleanup_on_removal(self) -> None:
        """Test that cache entries are cleaned up.

        When skills/directories are removed.
        """
        skill_dir = self._create_skill_dir("test_skill", "A test skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()

        abs_skill_dir = os.path.abspath(skill_dir)
        normalized_test_dir = os.path.abspath(self.test_dir)

        # Verify cache entries exist
        self.assertIn(abs_skill_dir, self.manager._skill_dir_mtime_cache)
        self.assertIn(
            normalized_test_dir,
            self.manager._monitored_dir_last_scan_mtime,
        )

        # Remove monitored directory
        self.manager.remove_monitored_directory(self.test_dir)

        # Verify cache entries cleaned up
        self.assertNotIn(
            normalized_test_dir,
            self.manager._monitored_dir_last_scan_mtime,
        )
        self.assertEqual(len(self.manager._skill_dir_mtime_cache), 0)


class SkillManagerChangeDetectionTest(TestCase):
    """Test change detection.

    Additions, modifications, deletions, and name changes.
    """

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.test_dir = tempfile.mkdtemp()
        self.manager = AgentSkillManager(
            agent_skill_instruction="Test instruction: {skills}",
            agent_skill_template="Skill: {name} - {description} ({dir})",
        )

    def tearDown(self) -> None:
        """Clean up test environment after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_skill_dir(self, name: str, description: str) -> str:
        """Helper to create a valid skill directory with SKILL.md."""
        skill_dir = os.path.join(self.test_dir, name)
        os.makedirs(skill_dir, exist_ok=True)

        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"name: {name}\n")
            f.write(f"description: {description}\n")
            f.write("---\n")

        return skill_dir

    # Addition Detection Tests
    def test_detect_new_skills(self) -> None:
        """Test detection of new skills.

        Single and multiple.
        """
        self._create_skill_dir("skill1", "First skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 1)

        # Add multiple new skills
        time.sleep(0.01)
        skill2_dir = self._create_skill_dir("skill2", "Second skill")
        self._create_skill_dir("skill3", "Third skill")

        self.manager.get_agent_skill_prompt()

        # Verify all skills discovered
        self.assertEqual(len(self.manager.skills), 3)
        self.assertIn("skill1", self.manager.skills)
        self.assertIn("skill2", self.manager.skills)
        self.assertIn("skill3", self.manager.skills)

        # Verify metadata correct
        skill2 = self.manager.skills["skill2"]
        self.assertEqual(skill2["name"], "skill2")
        self.assertEqual(skill2["description"], "Second skill")
        self.assertEqual(skill2["dir"], os.path.abspath(skill2_dir))
        self.assertEqual(skill2["source"], "monitored")

    # Modification Detection Tests
    def test_detect_modified_skills(self) -> None:
        """Test detection of skill modifications.

        Description and content changes.
        """
        skill_dir = self._create_skill_dir(
            "test_skill",
            "Original description",
        )

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(
            self.manager.skills["test_skill"]["description"],
            "Original description",
        )

        # Modify description
        time.sleep(0.01)
        with open(
            os.path.join(skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: test_skill\n"
                "description: Modified description\n---\n",
            )
        os.utime(skill_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify description updated
        self.assertEqual(
            self.manager.skills["test_skill"]["description"],
            "Modified description",
        )
        self.assertEqual(len(self.manager.skills), 1)

    # Deletion Detection Tests
    def test_detect_deleted_skills(self) -> None:
        """Test detection of deleted skills.

        Single and multiple.
        """
        skill1_dir = self._create_skill_dir("skill1", "First skill")
        skill2_dir = self._create_skill_dir("skill2", "Second skill")
        self._create_skill_dir("skill3", "Third skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 3)

        # Delete two skills
        time.sleep(0.01)
        shutil.rmtree(skill1_dir)
        shutil.rmtree(skill2_dir)

        self.manager.get_agent_skill_prompt()

        # Verify deleted skills removed
        self.assertEqual(len(self.manager.skills), 1)
        self.assertNotIn("skill1", self.manager.skills)
        self.assertNotIn("skill2", self.manager.skills)
        self.assertIn("skill3", self.manager.skills)

        # Verify cache cleaned up
        self.assertNotIn(
            os.path.abspath(skill1_dir),
            self.manager._skill_dir_mtime_cache,
        )

    def test_detect_all_skills_deleted(self) -> None:
        """Test that deleting all skills results in empty dict.

        None prompt.
        """
        skill1_dir = self._create_skill_dir("skill1", "First skill")
        skill2_dir = self._create_skill_dir("skill2", "Second skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 2)

        # Delete all skills
        time.sleep(0.01)
        shutil.rmtree(skill1_dir)
        shutil.rmtree(skill2_dir)

        prompt = self.manager.get_agent_skill_prompt()

        # Verify all removed and prompt is None
        self.assertEqual(len(self.manager.skills), 0)
        self.assertIsNone(prompt)

    # Name Change Detection Tests
    def test_detect_skill_name_change(self) -> None:
        """Test detection of skill name changes."""
        skill_dir = self._create_skill_dir("old_name", "A test skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertIn("old_name", self.manager.skills)

        # Change name
        time.sleep(0.01)
        with open(
            os.path.join(skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("---\nname: new_name\ndescription: A test skill\n---\n")
        os.utime(skill_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify old name removed, new name added
        self.assertEqual(len(self.manager.skills), 1)
        self.assertNotIn("old_name", self.manager.skills)
        self.assertIn("new_name", self.manager.skills)
        self.assertEqual(
            self.manager.skills["new_name"]["dir"],
            os.path.abspath(skill_dir),
        )

    def test_detect_name_change_with_description_change(self) -> None:
        """Test detection of both name and description changes."""
        skill_dir = self._create_skill_dir("old_name", "Old description")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()

        # Change both
        time.sleep(0.01)
        with open(
            os.path.join(skill_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("---\nname: new_name\ndescription: New description\n---\n")
        os.utime(skill_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify both changes applied
        self.assertNotIn("old_name", self.manager.skills)
        self.assertIn("new_name", self.manager.skills)
        self.assertEqual(
            self.manager.skills["new_name"]["description"],
            "New description",
        )

    def test_name_change_conflict_handling(self) -> None:
        """Test that name change conflicts with existing skills.

        Are handled.
        """
        skill1_dir = self._create_skill_dir("skill1", "First skill")
        self._create_skill_dir("skill2", "Second skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 2)

        # Try to rename skill1 to skill2 (conflict)
        time.sleep(0.01)
        with open(
            os.path.join(skill1_dir, "SKILL.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                "---\nname: skill2\ndescription: First skill renamed\n---\n",
            )
        os.utime(skill1_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify conflict handled (existing skill2 kept, skill1 removed)
        self.assertIn("skill2", self.manager.skills)
        self.assertNotIn("skill1", self.manager.skills)
        self.assertEqual(
            self.manager.skills["skill2"]["description"],
            "Second skill",
        )

    # SKILL.md Deletion Tests
    def test_detect_skill_md_deletion(self) -> None:
        """Test detection of SKILL.md deletion removes skill."""
        skill1_dir = self._create_skill_dir("skill1", "First skill")
        self._create_skill_dir("skill2", "Second skill")

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertEqual(len(self.manager.skills), 2)

        # Delete SKILL.md from skill1
        time.sleep(0.01)
        os.remove(os.path.join(skill1_dir, "SKILL.md"))
        os.utime(skill1_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify skill1 removed, skill2 remains
        self.assertEqual(len(self.manager.skills), 1)
        self.assertNotIn("skill1", self.manager.skills)
        self.assertIn("skill2", self.manager.skills)

        # Verify cache cleaned up
        self.assertNotIn(
            os.path.abspath(skill1_dir),
            self.manager._skill_dir_mtime_cache,
        )

    def test_skill_md_deletion_and_recreation(self) -> None:
        """Test that recreating SKILL.md after deletion.

        Re-adds the skill.
        """
        skill_dir = self._create_skill_dir(
            "test_skill",
            "Original description",
        )

        self.manager.monitor_agent_skills(self.test_dir)
        self.manager.get_agent_skill_prompt()
        self.assertIn("test_skill", self.manager.skills)

        # Delete SKILL.md
        time.sleep(0.01)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        os.remove(skill_md_path)
        os.utime(skill_dir, None)
        os.utime(self.test_dir, None)

        self.manager.get_agent_skill_prompt()
        self.assertNotIn("test_skill", self.manager.skills)

        # Recreate with different description
        time.sleep(0.01)
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(
                "---\nname: test_skill\n"
                "description: Recreated description\n---\n",
            )
        os.utime(skill_dir, None)
        os.utime(self.test_dir, None)

        self.manager.get_agent_skill_prompt()

        # Verify skill re-added with new description
        self.assertIn("test_skill", self.manager.skills)
        self.assertEqual(
            self.manager.skills["test_skill"]["description"],
            "Recreated description",
        )
