import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
import json
from config import CONFIG
from models.quiz_view import QuizView, QuizCreationView
from utils.helpers import has_required_role, parse_options
from utils.db_utilsv2 import (
    get_question,
    get_all_quizzes,
    add_question,
    update_question,
    get_quiz_questions,
    update_quiz_name,
    get_quiz_name,
    get_leaderboards,
    check_quiz_exists,
    delete_quiz
)

logger = logging.getLogger('badgey.quiz_commands')

class QuizCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="create_quiz", description="Create a new quiz")
    async def create_quiz(self, interaction: discord.Interaction):
        # Check if user has required roles
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message(
                "Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", 
                ephemeral=True,
                delete_after=5
            )
            return

        try:
            view = QuizCreationView(interaction)
            await interaction.response.send_message("Let's create a quiz!", view=view, ephemeral=True)
            logger.info(f"Quiz creation started by {interaction.user.name}")
        except Exception as e:
            logger.error(f"Error in create_quiz: {e}")
            await interaction.response.send_message(f"Oops! Something went wrong: {e}", ephemeral=True)

    #Delete Quiz and Questions
    @app_commands.command(name="delete_quiz", description="Deletes a quiz")
    @app_commands.describe(
        quizid="The ID of the quiz"
    )
    async def delete_quiz_command(self, interaction: discord.Interaction, quizid: int):

        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message(
                "Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", 
                ephemeral=True,
                delete_after=5
            )
            return

        try:
            quiz_id = await get_quiz_name(quizid) #check if the quiz exist

            if not quiz_id:
                await interaction.response.send_message(f"Quiz {quizid} does not exist", ephemeral=True)
                return
            else:
                await delete_quiz(quizid)
                await interaction.response.send_message(f"Quiz {quiz_id} has beed deleted", ephemeral=True)
                return

        except Exception as e:
            await interaction.response.send_message(f"Oops! Something went wrong: {e}", ephemeral=True)

    # List all quizzes
    @app_commands.command(name="list_quizzes", description="List all available quizzes")
    async def list_quizzes(self, interaction: discord.Interaction):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            quizzes = await get_all_quizzes()
            
            if not quizzes:
                await interaction.followup.send("No quizzes found in the database.")
                return
            
            # Create an embed with the quiz list
            embed = discord.Embed(
                title="Available Quizzes",
                description="Here are all the quizzes you can start or edit:",
                color=discord.Color.blue()
            )
            
            for quiz in quizzes:
                quiz_id = quiz[0]
                quiz_name = quiz[1]
                questions = await get_quiz_questions(quiz_id)
                question_count = len(questions) if questions else 0
                
                embed.add_field(
                    name=f"ID: {quiz_id} - {quiz_name}",
                    value=f"Questions: {question_count}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing quizzes: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}")
    
    # Add question (slash command)
    @app_commands.command(name="add_question", description="Add a question to a quiz")
    @app_commands.describe(
        quiz_id="The ID of the quiz",
        question="The question text",
        options="Options in format 'A:Option 1 B:Option 2 C:Option 3'",
        correct_answer="The correct option (A, B, C, etc.)",
        points="Points for this question",
        explanation="Explanation for the correct answer (optional)"
    )
    async def add_question_command(
        self, 
        interaction: discord.Interaction, 
        quiz_id: int, 
        question: str,
        options: str,
        correct_answer: str,
        points: int = 10,
        explanation: str = None
    ):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse options
            try:
                options_dict = parse_options(options)
            except ValueError:
                await interaction.followup.send("Invalid options format. Please use format like 'A:Option 1 B:Option 2'", ephemeral=True)
                return
            
            # Validate correct answer
            if correct_answer not in options_dict:
                await interaction.followup.send(f"Correct answer '{correct_answer}' not found in provided options.", ephemeral=True)
                return
            
            # Add question to database
            await add_question(quiz_id, question, options_dict, correct_answer, points, explanation)
            
            await interaction.followup.send(f"Question added successfully to quiz ID {quiz_id}!", ephemeral=True)
            logger.info(f"Question added to quiz {quiz_id} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error adding question: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    # Edit question (slash command)
    @app_commands.command(name="edit_question", description="Edit an existing question")
    @app_commands.describe(
        question_id="The ID of the question to edit",
        question="New question text (leave empty to keep current)",
        options="New options in format 'A:Option 1 B:Option 2 C:Option 3' (leave empty to keep current)",
        correct_answer="New correct option (leave empty to keep current)",
        points="New points value (leave empty to keep current)"
    )
    async def edit_question_command(
        self, 
        interaction: discord.Interaction, 
        question_id: int,
        question: Optional[str] = None,
        options: Optional[str] = None,
        correct_answer: Optional[str] = None,
        points: Optional[int] = None
    ):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get existing question data
            question_data = await get_question(question_id)
            if not question_data:
                await interaction.followup.send(f"Question with ID {question_id} not found.", ephemeral=True)
                return
            
            # Parse current options
            current_options = json.loads(question_data[3])
            
            # Parse new options if provided
            new_options = None
            if options:
                try:
                    options_str = parse_options(options)
                    new_options = json.loads(options_str)  # Parse the JSON string to a dict
                except ValueError:
                    await interaction.followup.send("Invalid options format. Please use format like 'A:Option 1 B:Option 2'", ephemeral=True)
                    return
            
            # Validate new correct answer if provided
            if correct_answer:
                option_set = new_options if new_options else current_options
                if correct_answer not in option_set:
                    await interaction.followup.send(f"Correct answer '{correct_answer}' not found in options.", ephemeral=True)
                    return
            
            # Use existing values if new ones are not provided
            updated_question = question if question is not None else question_data[2]
            updated_options = new_options if new_options is not None else current_options
            updated_correct = correct_answer if correct_answer is not None else question_data[4]
            updated_points = points if points is not None else question_data[5]
            
            # Update the question
            await update_question(
                question_id,
                updated_question,
                updated_options,
                updated_correct,
                updated_points
            )

            logger.info(updated_question, updated_options, updated_correct, updated_points, new_options)
            await interaction.followup.send(f"Question ID {question_id} updated successfully!", ephemeral=True)
            logger.info(f"Question {question_id} updated by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error editing question: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    # Edit quiz name (slash command)
    @app_commands.command(name="edit_quiz", description="Edit a quiz's name")
    @app_commands.describe(
        quiz_id="The ID of the quiz to edit",
        new_name="The new name for the quiz"
    )
    async def edit_quiz_command(
        self,
        interaction: discord.Interaction,
        quiz_id: int,
        new_name: str
    ):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Update quiz name
            success = await update_quiz_name(quiz_id, new_name)
            
            if success:
                await interaction.followup.send(f"Quiz ID {quiz_id} renamed to '{new_name}' successfully!", ephemeral=True)
                logger.info(f"Quiz {quiz_id} renamed to '{new_name}' by {interaction.user.name}")
            else:
                await interaction.followup.send(f"Quiz with ID {quiz_id} not found.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error editing quiz: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    # List quiz questions (slash command)
    @app_commands.command(name="list_questions", description="Show Questions on a quiz")
    @app_commands.describe(
        quiz_id="The ID of the quiz to show questions"
    )
    async def list_questions_command(
        self,
        interaction: discord.Interaction,
        quiz_id: int,
    ):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # First get the quiz name
            quiz_result = await get_quiz_name(quiz_id)
                    
            if not quiz_result:
                await interaction.followup.send(f"No quiz found with ID {quiz_id}.")
                return
                
            quiz_name = quiz_result[0]
            questions = await get_quiz_questions(quiz_id)
            
            if not questions:
                await interaction.followup.send(f"No questions found in quiz '{quiz_name}' (ID: {quiz_id}).")
                return
            
            # Create an embed with the questions list
            embed = discord.Embed(
                title=f"Questions for Quiz: {quiz_name}",
                description=f"Quiz ID: {quiz_id} - Total Questions: {len(questions)}",
                color=discord.Color.blue()
            )
            
            for question in questions:
                question_id = question[0]
                question_text = question[2]
                options = json.loads(question[3])
                correct_answer = question[4]
                points = question[5]
                
                # Format options for display
                # Safely handle options regardless of whether they're a string or a dictionary
                if isinstance(options, str):
                    options_text = options
                else:
                    try:
                        options_text = "\n".join([f"{key}: {value}" for key, value in options.items()])
                    except AttributeError:
                        options_text = str(options)  # Fallback for any other type
                
                embed.add_field(
                    name=f"Question ID: {question_id}",
                    value=f"**Question:** {question_text}\n**Options:**\n{options_text}\n**Correct Answer:** {correct_answer}\n**Points:** {points}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing questions: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}")

 # Leaderboard command
    @app_commands.command(name="leaderboard", description="Show top users by quiz score")
    @app_commands.describe(
        quiz_ids="Comma-separated quiz IDs to include (leave blank for all quizzes)",
        limit="Number of top users to display (default 10, max 25)"
    )
    async def leaderboard_command(
        self, 
        interaction: discord.Interaction, 
        quiz_ids: Optional[str] = None,
        limit: Optional[int] = 10
    ):
        # Validate limit
        limit = max(1, min(limit or 10, 25))
        
        # Check if user has required roles
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message(
                "Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Parse quiz IDs if provided
            parsed_quiz_ids = []
            if quiz_ids:
                try:
                    parsed_quiz_ids = [int(id.strip()) for id in quiz_ids.split(',')]
                except ValueError:
                    await interaction.followup.send("Invalid quiz ID format. Please use comma-separated numbers.", ephemeral=True)
                    return
            
            # Fetch leaderboard data based on quiz selection
            leaderboard_data = await get_leaderboards(limit,parsed_quiz_ids) 
            
            # Handle no results
            if not leaderboard_data:
                # Check if specified quiz IDs exist
                if parsed_quiz_ids:
                    # Verify quiz existence
                    existing_quizzes = check_quiz_exists(parsed_quiz_ids)
                    
                    if not existing_quizzes:
                        await interaction.followup.send(f"No quizzes found with IDs: {quiz_ids}", ephemeral=True)
                    else:
                        # Some quizzes exist, but no scores
                        quiz_names = ', '.join([f"{quiz[0]}: {quiz[1]}" for quiz in existing_quizzes])
                        await interaction.followup.send(f"No scores found for quizzes: {quiz_names}", ephemeral=True)
                else:
                    await interaction.followup.send("No leaderboard data available yet.", ephemeral=True)
                return
            
            # Create an embed to display the leaderboard
            embed = discord.Embed(
                title="🏆 Quiz Leaderboard 🏆",
                color=discord.Color.gold()
            )
            
            # Set description based on quiz selection
            if parsed_quiz_ids:
                # Fetch quiz names for the selected IDs
                quiz_names = await check_quiz_exists(parsed_quiz_ids)
                quiz_names = [row['quiz_name'] for row in quiz_names]  # Use dictionary key
                
                embed.description = f"Top {limit} Users - Quizzes: {', '.join(quiz_names)}"
            else:
                embed.description = f"Top {limit} Users Across All Quizzes"

            # Add leaderboard entries
            for index, entry in enumerate(leaderboard_data, 1):
                # Use medal emojis for top 3 positions
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(index, "")
                
                embed.add_field(
                    name=f"{medal} {index}. {entry['user_name']}",
                    value=f"Total Score: {entry['total_score']}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error generating leaderboard: {e}")
            await interaction.followup.send(f"An error occurred while fetching the leaderboard: {str(e)}")   
            
async def setup(bot):
    cog = QuizCommandsCog(bot)
    await bot.add_cog(cog)