"""Squash migration for PostgreSQL — all tables

Revision ID: 017_squash_postgresql
Revises:
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '017_squash_postgresql'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── quests ────────────────────────────────
    op.create_table('quests',
        sa.Column('qid', sa.Integer(), nullable=False),
        sa.Column('players', sa.Text(), nullable=False),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('endxp', sa.Integer(), nullable=False),
        sa.Column('currentxp', sa.Integer(), nullable=False),
        sa.Column('deadline', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('qid'),
    )

    # ── player_quests ─────────────────────────
    op.create_table('player_quests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('quest_id', sa.Integer(), server_default=sa.text('0')),
        sa.Column('quest_id_str', sa.String(length=50), server_default=sa.text("''")),
        sa.Column('location_name', sa.String(length=100), server_default=sa.text("''")),
        sa.Column('location_x', sa.Integer(), server_default=sa.text('0')),
        sa.Column('location_y', sa.Integer(), server_default=sa.text('0')),
        sa.Column('quest_key', sa.String(length=36), unique=True, server_default=sa.text("''")),
        sa.Column('quest_type', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=30)),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('location_id', sa.String(length=30), server_default=sa.text("''")),
        sa.Column('target_type', sa.String(length=20), server_default=sa.text("''")),
        sa.Column('target_id', sa.String(length=50), server_default=sa.text("''")),
        sa.Column('target_count', sa.Integer(), server_default=sa.text('1')),
        sa.Column('progress', sa.Integer(), server_default=sa.text('0')),
        sa.Column('reward_xp', sa.Integer(), server_default=sa.text('0')),
        sa.Column('reward_gold', sa.Integer(), server_default=sa.text('0')),
        sa.Column('reward_item', sa.String(length=100), server_default=sa.text("''")),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'offered'")),
        sa.Column('expires_at', sa.Integer(), server_default=sa.text('0')),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('accepted_at', sa.Integer(), server_default=sa.text('0')),
        sa.Column('completed_at', sa.Integer(), server_default=sa.text('0')),
        sa.Column('location_locked', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('target_location_id', sa.String(length=50), server_default=sa.text("''")),
        sa.Column('cooldown_until', sa.Integer(), server_default=sa.text('0')),
        sa.Column('last_progress_at', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_player_quests_player_uid', 'player_quests', ['player_uid'])

    # ── bosses ────────────────────────────────
    op.create_table('bosses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('boss_id', sa.String(length=20), nullable=False, unique=True),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('location_name', sa.String(length=100), nullable=False),
        sa.Column('x', sa.Integer(), nullable=False),
        sa.Column('y', sa.Integer(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('equipment', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('defeated', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('defeated_at', sa.Integer(), server_default=sa.text('0')),
        sa.Column('defeated_by', sa.BigInteger(), server_default=sa.text('0')),
        sa.Column('respawn_available', sa.Integer(), server_default=sa.text('0')),
        sa.Column('respawn_cost', sa.Integer(), server_default=sa.text('50')),
        sa.Column('difficulty', sa.String(length=20), server_default=sa.text("'medium'")),
        sa.Column('legendary_counter', sa.Integer(), server_default=sa.text('0')),
        sa.Column('wins', sa.Integer(), server_default=sa.text('0')),
        sa.Column('hp', sa.Integer(), server_default=sa.text('500')),
        sa.Column('max_hp', sa.Integer(), server_default=sa.text('500')),
        sa.Column('mp', sa.Integer(), server_default=sa.text('100')),
        sa.Column('max_mp', sa.Integer(), server_default=sa.text('100')),
        sa.Column('defense', sa.Integer(), server_default=sa.text('10')),
        sa.Column('skills', sa.JSON(none_as_null=True), server_default=sa.text("'[]'::jsonb")),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── users ─────────────────────────────────
    op.create_table('users',
        sa.Column('uid', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('level', sa.Integer(), server_default=sa.text('1')),
        sa.Column('job', sa.String(length=100), server_default=sa.text("''")),
        sa.Column('align', sa.Integer(), server_default=sa.text('0')),
        sa.Column('nextxp', sa.Integer(), server_default=sa.text('600')),
        sa.Column('currentxp', sa.Integer(), server_default=sa.text('0')),
        sa.Column('totalxp', sa.Integer(), server_default=sa.text('0')),
        sa.Column('totalxplost', sa.Integer(), server_default=sa.text('0')),
        sa.Column('online', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created', sa.Integer(), nullable=False),
        sa.Column('lastlogin', sa.Integer(), nullable=False),
        sa.Column('x', sa.Integer(), server_default=sa.text('500')),
        sa.Column('y', sa.Integer(), server_default=sa.text('500')),
        sa.Column('wins', sa.Integer(), server_default=sa.text('0')),
        sa.Column('loss', sa.Integer(), server_default=sa.text('0')),
        sa.Column('totalquests', sa.Integer(), server_default=sa.text('0')),
        sa.Column('onquest', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('qid', sa.Integer(), server_default=sa.text('0')),
        sa.Column('optin', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('auto_accept_quests', sa.String(length=10), server_default=sa.text("'off'")),
        sa.Column('auto_quest_unlocked', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('lang', sa.String(length=5), server_default=sa.text("''")),
        sa.Column('race', sa.String(length=20), server_default=sa.text("''")),
        sa.Column('onboarding_done', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('state', sa.String(length=20), server_default=sa.text("'peaceful'")),
        sa.Column('state_context', sa.Text(), server_default=sa.text("'{}'")),
        sa.Column('tokens', sa.Integer(), server_default=sa.text('0')),
        sa.Column('gold', sa.Integer(), server_default=sa.text('0')),
        sa.Column('idle_since', sa.Integer(), server_default=sa.text('0')),
        sa.Column('idle_xp', sa.Integer(), server_default=sa.text('0')),
        sa.Column('xp_boost_until', sa.Integer(), server_default=sa.text('0')),
        sa.Column('speed_boost_until', sa.Integer(), server_default=sa.text('0')),
        sa.Column('protect_until', sa.Integer(), server_default=sa.text('0')),
        sa.Column('prestige_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('prestige_bonus', sa.Integer(), server_default=sa.text('0')),
        sa.Column('prestige_level', sa.Integer(), server_default=sa.text('0')),
        sa.Column('prestige_xp_level', sa.Integer(), server_default=sa.text('0')),
        sa.Column('prestige_gold_level', sa.Integer(), server_default=sa.text('0')),
        sa.Column('quest_cooldown', sa.Integer(), server_default=sa.text('0')),
        sa.Column('hp', sa.Integer(), server_default=sa.text('100')),
        sa.Column('max_hp', sa.Integer(), server_default=sa.text('100')),
        sa.Column('mp', sa.Integer(), server_default=sa.text('50')),
        sa.Column('max_mp', sa.Integer(), server_default=sa.text('50')),
        sa.Column('defense', sa.Integer(), server_default=sa.text('0')),
        sa.Column('fight_streak', sa.Integer(), server_default=sa.text('0')),
        sa.Column('monster_kills', sa.Integer(), server_default=sa.text('0')),
        sa.Column('monster_deaths', sa.Integer(), server_default=sa.text('0')),
        sa.Column('weapon', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('shield', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('helmet', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('chest', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('gloves', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('boots', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('ring', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.Column('amulet', sa.JSON(none_as_null=True), server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint('uid'),
    )
    op.create_index('idx_users_online', 'users', ['online'])
    op.create_index('idx_users_online_lastlogin', 'users', ['online', 'lastlogin'])
    op.create_index('idx_users_xy', 'users', ['x', 'y'])
    op.create_index('idx_users_state', 'users', ['state'])
    op.create_index('idx_users_onquest_online', 'users', ['onquest', 'online'])
    op.create_index('idx_users_level_totalxp', 'users', [sa.text('level DESC'), sa.text('totalxp DESC')])

    # ── clans ─────────────────────────────────
    op.create_table('clans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('tag', sa.String(length=10), server_default=sa.text("''")),
        sa.Column('leader_uid', sa.BigInteger(), nullable=False),
        sa.Column('description', sa.Text(), server_default=sa.text("''")),
        sa.Column('bank_gold', sa.Integer(), server_default=sa.text('0')),
        sa.Column('level', sa.Integer(), server_default=sa.text('1')),
        sa.Column('xp', sa.Integer(), server_default=sa.text('0')),
        sa.Column('icon', sa.String(length=20), server_default=sa.text("''")),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_clans_name', 'clans', ['name'])
    op.create_index('idx_clans_leader', 'clans', ['leader_uid'])

    # ── clan_members ──────────────────────────
    op.create_table('clan_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=20), server_default=sa.text("'member'")),
        sa.Column('joined_at', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), server_default=sa.text('0')),
        sa.Column('total_donated', sa.Integer(), server_default=sa.text('0')),
        sa.Column('last_donated', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clan_id', 'player_uid'),
    )
    op.create_index('idx_clan_members_clan', 'clan_members', ['clan_id'])
    op.create_index('idx_clan_members_player', 'clan_members', ['player_uid'])

    # ── clan_applications ─────────────────────
    op.create_table('clan_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False),
        sa.Column('message', sa.Text(), server_default=sa.text("''")),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'")),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('reviewed_at', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_clan_apps_clan', 'clan_applications', ['clan_id'])
    op.create_index('idx_clan_apps_player', 'clan_applications', ['player_uid'])
    op.create_index('idx_clan_apps_pending', 'clan_applications', ['clan_id', 'status'])

    # ── clan_invites ──────────────────────────
    op.create_table('clan_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False),
        sa.Column('invited_by', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'")),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_clan_invites_player', 'clan_invites', ['player_uid', 'status'])
    op.create_index('idx_clan_invites_expires', 'clan_invites', ['expires_at'])

    # ── player_passives ───────────────────────
    op.create_table('player_passives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('passive_id', sa.String(length=50), nullable=False),
        sa.Column('level', sa.Integer(), server_default=sa.text('1')),
        sa.Column('xp_progress', sa.Integer(), server_default=sa.text('0')),
        sa.Column('equipped', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('acquired_at', sa.Integer(), server_default=sa.text('0')),
        sa.Column('cooldown_until', sa.Integer(), server_default=sa.text('0')),
        sa.Column('last_triggered_at', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_player_passives_uid', 'player_passives', ['player_uid'])

    # ── player_active_skills ──────────────────
    op.create_table('player_active_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('player_uid', sa.BigInteger(), nullable=False, index=True),
        sa.Column('skill_id', sa.String(length=50), nullable=False),
        sa.Column('level', sa.Integer(), server_default=sa.text('1')),
        sa.Column('xp_progress', sa.Integer(), server_default=sa.text('0')),
        sa.Column('use_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('acquired_at', sa.Integer(), server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_player_active_skills_uid', 'player_active_skills', ['player_uid'])

    # ── star_purchases ────────────────────────
    op.create_table('star_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('tokens_amount', sa.Integer(), nullable=False),
        sa.Column('stars_amount', sa.Integer(), nullable=False),
        sa.Column('telegram_payment_charge_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('purchased_at', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_star_purchases_user', 'star_purchases', ['user_id'])
    op.create_index('idx_star_purchases_charge', 'star_purchases', ['telegram_payment_charge_id'])
    op.create_index('idx_star_purchases_date', 'star_purchases', ['purchased_at'])


def downgrade() -> None:
    op.drop_table('star_purchases')
    op.drop_table('player_active_skills')
    op.drop_table('player_passives')
    op.drop_table('clan_invites')
    op.drop_table('clan_applications')
    op.drop_table('clan_members')
    op.drop_table('clans')
    op.drop_table('users')
    op.drop_table('bosses')
    op.drop_table('player_quests')
    op.drop_table('quests')
